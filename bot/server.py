"""
FastAPI HTTP server for the PokeChess bot engine.

Exposes:
  POST /move   — deserialize state, run MCTS, return chosen move
  GET  /health — liveness check

Global process state:
  global_tt       TranspositionTable shared across all requests (inter-game learning)
  request_count   total POST /move requests served; triggers TT backup every 50 requests
  sync_queue      TTSyncQueue that saves TT to disk and optionally uploads to S3
"""

from __future__ import annotations

import atexit
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from bot.mcts import MCTS
from bot.transposition import TranspositionTable
from bot.tt_store import TTSyncQueue, TTStore
from engine.state import GameState

logger = logging.getLogger(__name__)

# Persona floats from HTTP JSON — clamp so callers cannot distort UCB1 with
# extreme exploration_c or bias_bonus (time_budget is capped the same way).
_EXPLORATION_C_MIN = 0.05
_EXPLORATION_C_MAX = 10.0
_BIAS_BONUS_MIN = 0.0
_BIAS_BONUS_MAX = 3.0

# ---------------------------------------------------------------------------
# Module-level process state (initialised in lifespan)
# ---------------------------------------------------------------------------

# Read desired slot count from env.  Default 1M (16 MB) is safe for dev/tests.
# Set POKECHESS_TT_SIZE=67108864 (64M, ~1 GB) in production.
_tt_size: int = int(os.environ.get("POKECHESS_TT_SIZE", 1 << 20))

global_tt: TranspositionTable = TranspositionTable(size=_tt_size)
request_count: int = 0
sync_queue: Optional[TTSyncQueue] = None

# Asyncio lock — ensures at most one MCTS search runs at a time so two
# simultaneous requests don't thrash the CPU.
import asyncio
_mcts_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# No-op store — used when POKECHESS_TT_BUCKET is not configured
# ---------------------------------------------------------------------------

class _NoOpStore:
    """Drop-in TTStore replacement that silently discards upload calls."""

    def download(self, local_path: str) -> bool:  # noqa: D102
        return False

    def upload(self, local_path: str) -> None:  # noqa: D102
        pass


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_tt, sync_queue

    local_path = os.environ.get("POKECHESS_TT_LOCAL_PATH", "transposition_table.bin")
    bucket = os.environ.get("POKECHESS_TT_BUCKET", "")
    version = os.environ.get("POKECHESS_TT_VERSION", "1")

    store: Any  # TTStore or _NoOpStore

    if os.path.exists(local_path):
        logger.info("Loading TT from local file: %s", local_path)
        global_tt.load(local_path)
        store = TTStore(bucket, f"tt_v{version}.bin") if bucket else _NoOpStore()
    elif bucket:
        store = TTStore(bucket, f"tt_v{version}.bin")
        logger.info("Attempting to download TT from S3 bucket=%s key=tt_v%s.bin", bucket, version)
        try:
            downloaded = store.download(local_path)
        except Exception:
            # S3 is a warm-start optimisation — a misconfigured bucket or
            # transient network error must not prevent the engine from serving.
            logger.exception(
                "Failed to download TT from S3; starting with empty TT. "
                "Check POKECHESS_TT_BUCKET, POKECHESS_TT_VERSION, and AWS credentials."
            )
            downloaded = False
        if downloaded:
            logger.info("Downloaded TT from S3; loading.")
            global_tt.load(local_path)
        else:
            logger.info("TT key not found in S3; starting with empty TT.")
    else:
        logger.info("No local TT and no S3 bucket configured; starting with empty TT.")
        store = _NoOpStore()

    sync_queue = TTSyncQueue(global_tt, store, local_path)
    atexit.register(sync_queue.drain)

    yield

    # Shutdown: drain any pending backup before the process exits.
    sync_queue.drain()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="PokeChess Bot Engine", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class PersonaParams(BaseModel):
    time_budget: float = 3.0
    exploration_c: Optional[float] = None
    use_transposition: bool = True
    move_bias: Optional[str] = None
    bias_bonus: float = 0.15

    model_config = {"extra": "allow"}  # forward unknown keys without error


class MoveRequest(BaseModel):
    state: dict
    persona_params: PersonaParams = PersonaParams()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/move")
async def get_move(body: MoveRequest):
    global request_count

    # 1. Deserialize state; strip hidden_items so the bot is blind to unexplored grass
    try:
        state = GameState.from_dict(body.state)
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid state: {exc}") from exc
    state.hidden_items = []

    # 2. Extract and clamp time_budget
    time_budget = max(0.1, min(10.0, body.persona_params.time_budget))

    # 3. Build MCTS kwargs from persona params
    mcts_kwargs: dict[str, Any] = {"time_budget": time_budget}
    if body.persona_params.use_transposition:
        mcts_kwargs["transposition"] = global_tt
    if body.persona_params.exploration_c is not None:
        exploration_c = max(
            _EXPLORATION_C_MIN,
            min(_EXPLORATION_C_MAX, body.persona_params.exploration_c),
        )
        mcts_kwargs["exploration_c"] = exploration_c
    if body.persona_params.move_bias is not None:
        mcts_kwargs["move_bias"] = body.persona_params.move_bias
        bias_bonus = max(
            _BIAS_BONUS_MIN,
            min(_BIAS_BONUS_MAX, body.persona_params.bias_bonus),
        )
        mcts_kwargs["bias_bonus"] = bias_bonus

    # 4. Run MCTS (one at a time — CPU-bound)
    async with _mcts_lock:
        loop = asyncio.get_running_loop()
        move = await loop.run_in_executor(None, _run_mcts, state, mcts_kwargs)

    # 5. Increment counter; enqueue TT backup every 50 requests
    request_count += 1
    if request_count % 50 == 0 and sync_queue is not None:
        sync_queue.enqueue()

    # 6. Return flat move dict
    if move is None:
        logger.error("MCTS returned None for state (turn=%d, active=%s)", state.turn_number, state.active_player)
        raise HTTPException(status_code=500, detail="Engine failed to select a move")
    return move.to_dict()


def _run_mcts(state: GameState, mcts_kwargs: dict) -> Any:
    """Run MCTS synchronously (called via executor so it doesn't block the event loop)."""
    bot = MCTS(**mcts_kwargs)
    return bot.select_move(state)
