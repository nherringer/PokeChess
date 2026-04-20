"""
httpx wrapper for communicating with the engine container.

The engine exposes POST /move which accepts the game state and a
persona_params dict, and returns the bot's chosen move.  The app calls
this during PvB games after the human submits their move.

Request payload shape:
    {"state": <FEN dict>, "persona_params": {"time_budget": <float>, ...}}

The engine reads persona_params["time_budget"] to set its MCTS search
deadline.  Additional keys in persona_params are reserved for future
tuning (e.g. exploration_c, rollout_depth_limit) and are passed through
unchanged so the engine can use them without an app change.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import Request

from . import config
from .main import AppError

logger = logging.getLogger(__name__)

# Cap engine HTTP wait so a bad DB bot_params.time_budget cannot hold row locks unbounded.
_MAX_BOT_TIME_BUDGET = 10.0
_MIN_BOT_TIME_BUDGET = 0.1


async def request_bot_move(
    request: Request,
    state_dict: dict,
    persona_params: dict,
) -> dict:
    """
    Ask the engine service to pick a move for the active player.

    persona_params must contain "time_budget" (float, seconds).  Any extra
    keys are forwarded verbatim so future tuning params need no code change
    on the app side.

    Returns the raw JSON response from the engine (a move dict).
    Raises AppError(503) on network/timeout failures.
    """
    try:
        tb = float(persona_params.get("time_budget", 3.0))
    except (TypeError, ValueError):
        tb = 3.0
    tb = max(_MIN_BOT_TIME_BUDGET, min(tb, _MAX_BOT_TIME_BUDGET))

    # Rebuild with the (possibly clamped) effective budget so the engine
    # never sees an out-of-range value regardless of what's in the DB.
    outgoing_params = {**persona_params, "time_budget": tb}

    client: httpx.AsyncClient = request.app.state.engine_client
    try:
        resp = await client.post(
            "/move",
            json={"state": state_dict, "persona_params": outgoing_params},
            headers={"X-Bot-Api-Secret": config.BOT_API_SECRET},
            timeout=tb + 5.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        logger.error("Engine returned HTTP %d: %s", status, body)
        if 400 <= status < 500:
            # 4xx means the app sent a bad request — surface as 502 so it's
            # distinguishable from a 5xx engine failure.
            raise AppError(502, "engine_request_error", f"Engine rejected request (HTTP {status})")
        raise AppError(503, "engine_error", "Engine returned an error")
    except (httpx.RequestError, httpx.TimeoutException):
        raise AppError(503, "engine_unavailable", "Engine is unreachable")
