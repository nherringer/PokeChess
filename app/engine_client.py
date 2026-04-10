"""
httpx wrapper for communicating with the engine container.

The engine exposes POST /move which accepts the game state and returns
the bot's chosen move. The app calls this during PvB games after the
human submits their move.
"""

from __future__ import annotations

import httpx
from fastapi import Request

from .main import AppError

# Cap engine HTTP wait so a bad DB `bot_params.time_budget` cannot hold row locks unbounded.
_MAX_BOT_TIME_BUDGET = 30.0
_MIN_BOT_TIME_BUDGET = 0.1


async def request_bot_move(
    request: Request,
    state_dict: dict,
    time_budget: float = 3.0,
) -> dict:
    """
    Ask the engine service to pick a move for the active player.

    Returns the raw JSON response from the engine (a move dict).
    Raises AppError(503) on network/timeout failures.
    """
    try:
        tb = float(time_budget)
    except (TypeError, ValueError):
        tb = 3.0
    tb = max(_MIN_BOT_TIME_BUDGET, min(tb, _MAX_BOT_TIME_BUDGET))

    client: httpx.AsyncClient = request.app.state.engine_client
    try:
        resp = await client.post(
            "/move",
            json={"state": state_dict, "time_budget": tb},
            timeout=tb + 5.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError:
        raise AppError(503, "engine_error", "Engine returned an error")
    except (httpx.RequestError, httpx.TimeoutException):
        raise AppError(503, "engine_unavailable", "Engine is unreachable")
