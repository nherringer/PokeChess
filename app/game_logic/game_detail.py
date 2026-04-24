"""Build `GameDetail` from a games table row dict with optional per-viewer masking."""

from __future__ import annotations

import json
from uuid import UUID

from ..schemas import GameDetail
from .serialization import mask_history_foresight, mask_state_dict


def user_team_name(game: dict, user_id: UUID) -> str | None:
    """Return ``\"RED\"`` or ``\"BLUE\"`` for masking helpers, or ``None`` if not a participant."""
    if game.get("red_player_id") == user_id:
        return "RED"
    if game.get("blue_player_id") == user_id:
        return "BLUE"
    return None


def game_dict_to_detail(game: dict, team_name: str | None = None) -> GameDetail:
    """
    Convert a game row dict to ``GameDetail``.

    When ``team_name`` is ``\"RED\"`` or ``\"BLUE\"``, ``state`` and ``move_history``
    are masked for fog-of-war; ``my_side`` is set to the lowercase team for the client.
    """
    state = game.get("state")
    history = game.get("move_history")
    # asyncpg returns JSONB as dicts/lists directly; some paths may still JSON-stringify.
    if isinstance(state, str):
        state = json.loads(state)
    if isinstance(history, str):
        history = json.loads(history)
    if state is not None and team_name is not None:
        state = mask_state_dict(state, team_name)
    if history is not None and team_name is not None:
        history = mask_history_foresight(history, team_name)
    return GameDetail(
        id=game["id"],
        status=game["status"],
        whose_turn=game.get("whose_turn"),
        turn_number=game["turn_number"],
        is_bot_game=game["is_bot_game"],
        bot_side=game.get("bot_side"),
        bot_name=game.get("bot_name"),
        red_player_id=game.get("red_player_id"),
        blue_player_id=game.get("blue_player_id"),
        winner=game.get("winner"),
        end_reason=game.get("end_reason"),
        state=state,
        move_history=history if history else [],
        my_side=team_name.lower() if team_name else None,
    )
