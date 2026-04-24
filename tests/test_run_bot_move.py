"""
Tests for run_bot_move: split-transaction flow (T2a + engine + T2b).

Covers the re-validation paths that guard against game state changing
during the engine HTTP call (resign, concurrent bot move application,
engine returning an illegal move). DB and engine are mocked — this does
not exercise real engine rules.
"""
from __future__ import annotations

import os

# app.config validates required env vars at import time. Set safe placeholders
# before any app.* import below so the module loads under pytest.
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 32)
os.environ.setdefault("BOT_API_SECRET", "x" * 32)
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("ENVIRONMENT", "development")

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from engine.moves import Move, ActionType

# Load app.main first to side-step a module-init order quirk: when
# app.routes.moves is imported as the entry point, app.auth is partially
# loaded before create_app() finishes resolving the route modules, and
# downstream `from ..auth import Db` fails. Starting at app.main lets
# create_app run cleanly.
import app.main  # noqa: F401
from app.routes.moves import run_bot_move


# ---------------------------------------------------------------------------
# Mock scaffolding
# ---------------------------------------------------------------------------

class _FakeConn:
    """Mock asyncpg connection exposing an async-context-manager transaction."""

    def transaction(self):
        @asynccontextmanager
        async def _cm():
            yield
        return _cm()


class _FakePool:
    """Mock asyncpg pool exposing an async-context-manager acquire."""

    def __init__(self):
        self._conn = _FakeConn()

    def acquire(self):
        conn = self._conn
        @asynccontextmanager
        async def _cm():
            yield conn
        return _cm()


def _fake_app():
    app = MagicMock()
    app.state.db_pool = _FakePool()
    app.state.engine_client = MagicMock()
    return app


def _row(*, status="active", whose_turn="blue", turn_number=2):
    """Minimal game row matching the shape get_game_for_move returns."""
    return {
        "id": uuid4(),
        "status": status,
        "whose_turn": whose_turn,
        "turn_number": turn_number,
        "is_bot_game": True,
        "bot_side": "blue",
        "bot_id": uuid4(),
        "state": {"active_player": "BLUE"},  # opaque — state_from_dict is mocked
        "move_history": [],
        "bot_params": {"time_budget": 0.5},
    }


def _engine_move_dict():
    return {
        "piece_row": 1,
        "piece_col": 0,
        "action_type": "MOVE",
        "target_row": 2,
        "target_col": 0,
        "secondary_row": None,
        "secondary_col": None,
        "move_slot": None,
    }


def _legal_move():
    return Move(
        piece_row=1, piece_col=0,
        action_type=ActionType.MOVE,
        target_row=2, target_col=0,
    )


@pytest.fixture
def mocks():
    """Patch every external dependency of run_bot_move and yield handles."""
    patchers = {
        "get_game_for_move": patch(
            "app.routes.moves.game_q.get_game_for_move", new_callable=AsyncMock
        ),
        "update_game_state": patch(
            "app.routes.moves.game_q.update_game_state", new_callable=AsyncMock
        ),
        "update_xp_earned": patch(
            "app.routes.moves.update_xp_earned", new_callable=AsyncMock
        ),
        "upsert_activity": patch(
            "app.db.queries.bot_activity.upsert_player_activity",
            new_callable=AsyncMock,
        ),
        "count_active": patch(
            "app.db.queries.bot_activity.count_active_bot_players",
            new_callable=AsyncMock,
        ),
        "call_bot_move": patch(
            "app.engine_client.call_bot_move", new_callable=AsyncMock
        ),
        "state_from_dict": patch("app.routes.moves.state_from_dict"),
        "state_to_dict": patch("app.routes.moves.state_to_dict"),
        "get_legal_moves": patch("app.routes.moves.get_legal_moves"),
        "apply_and_record": patch("app.routes.moves._apply_and_record"),
    }
    handles = {name: p.start() for name, p in patchers.items()}

    # Reasonable defaults
    handles["count_active"].return_value = 1
    handles["state_from_dict"].return_value = (MagicMock(), MagicMock())
    handles["state_to_dict"].return_value = {}
    handles["get_legal_moves"].return_value = [_legal_move()]
    handles["call_bot_move"].return_value = _engine_move_dict()

    new_state = MagicMock()
    new_state.active_player.name.lower.return_value = "red"
    new_state.turn_number = 3
    handles["apply_and_record"].return_value = (
        new_state, MagicMock(), [{}], False, None,
    )

    yield handles

    for p in patchers.values():
        p.stop()


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_happy_path_applies_bot_move(mocks):
    """T2a + engine + T2b complete successfully; update_game_state called once."""
    row = _row()
    mocks["get_game_for_move"].side_effect = [row, row]

    _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    assert mocks["call_bot_move"].await_count == 1
    assert mocks["update_game_state"].await_count == 1
    # Non-terminal: XP updater not invoked
    assert mocks["update_xp_earned"].await_count == 0


def test_resign_between_transactions_drops_move(mocks, caplog):
    """Status flips to 'complete' during engine call → T2b drops the move."""
    mocks["get_game_for_move"].side_effect = [
        _row(status="active"),
        _row(status="complete"),
    ]

    with caplog.at_level("INFO", logger="app.routes.moves"):
        _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    # Engine was called (no way to know status change before), but no write.
    assert mocks["call_bot_move"].await_count == 1
    assert mocks["update_game_state"].await_count == 0
    assert any("status changed to complete" in r.message for r in caplog.records)


def test_turn_number_drift_drops_move(mocks, caplog):
    """Concurrent application advances turn_number → T2b drops the move."""
    mocks["get_game_for_move"].side_effect = [
        _row(turn_number=2),
        _row(turn_number=3),
    ]

    with caplog.at_level("WARNING", logger="app.routes.moves"):
        _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    assert mocks["update_game_state"].await_count == 0
    assert any("turn_number=3" in r.message for r in caplog.records)


def test_illegal_engine_move_is_dropped(mocks, caplog):
    """Engine returns a move not in legal list → T2b drops, logs ERROR."""
    row = _row()
    mocks["get_game_for_move"].side_effect = [row, row]
    mocks["get_legal_moves"].return_value = []  # no moves match what engine sent

    with caplog.at_level("ERROR", logger="app.routes.moves"):
        _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    assert mocks["update_game_state"].await_count == 0
    assert any("illegal move" in r.message for r in caplog.records)


def test_terminal_move_updates_xp(mocks):
    """done=True path commits status='complete' and calls update_xp_earned."""
    row = _row()
    mocks["get_game_for_move"].side_effect = [row, row]

    new_state = MagicMock()
    new_state.active_player.name.lower.return_value = "red"
    new_state.turn_number = 3
    mocks["apply_and_record"].return_value = (
        new_state,
        MagicMock(),
        [{"action_type": "attack", "piece_id": "x", "result": {"damage": 120}}],
        True,
        "blue",
    )

    _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    assert mocks["update_game_state"].await_count == 1
    kwargs = mocks["update_game_state"].call_args.kwargs
    assert kwargs["status"] == "complete"
    assert kwargs["winner"] == "blue"
    assert kwargs["end_reason"] == "king_eliminated"
    assert mocks["update_xp_earned"].await_count == 1


def test_continue_bot_schedules_follow_up(mocks):
    """Bot keeps turn after a free action (e.g. TRADE) → asyncio.create_task called."""
    row = _row()  # bot_side="blue", whose_turn="blue"
    mocks["get_game_for_move"].side_effect = [row, row]

    new_state = MagicMock()
    new_state.active_player.name.lower.return_value = "blue"  # turn stays with bot
    new_state.turn_number = 3
    mocks["apply_and_record"].return_value = (
        new_state, MagicMock(), [{}], False, None,
    )

    with patch("app.routes.moves.asyncio.create_task") as mock_create_task:
        _run(run_bot_move(_fake_app(), uuid4(), uuid4()))

    assert mocks["update_game_state"].await_count == 1
    mock_create_task.assert_called_once()
