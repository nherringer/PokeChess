from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from engine.state import GameState

from ..auth import Db, CurrentUser
from ..main import AppError
from ..personas import get_persona
from ..schemas import CreateGameRequest, GameDetail, GameSummary, GamesListResponse
from ..game_logic.serialization import state_to_dict
from ..game_logic.roster import ensure_roster, build_id_map, create_game_pokemon_map
from ..db.queries import games as game_q
from .moves import _run_bot_move

router = APIRouter(prefix="/games", tags=["games"])


def _user_is_participant(game: dict, user_id: UUID) -> bool:
    return user_id in (game.get("red_player_id"), game.get("blue_player_id"))


def _game_detail(game: dict) -> GameDetail:
    state = game.get("state")
    history = game.get("move_history")
    # asyncpg returns JSONB as dicts/lists directly
    if isinstance(state, str):
        state = json.loads(state)
    if isinstance(history, str):
        history = json.loads(history)
    return GameDetail(
        id=game["id"],
        status=game["status"],
        whose_turn=game.get("whose_turn"),
        turn_number=game["turn_number"],
        is_bot_game=game["is_bot_game"],
        bot_side=game.get("bot_side"),
        red_player_id=game.get("red_player_id"),
        blue_player_id=game.get("blue_player_id"),
        winner=game.get("winner"),
        end_reason=game.get("end_reason"),
        state=state,
        move_history=history if history else [],
    )


@router.get("", response_model=GamesListResponse)
async def list_games(user: CurrentUser, db: Db):
    data = await game_q.list_games_for_user(db, user["id"])
    return GamesListResponse(
        active=[GameSummary(**g) for g in data["active"]],
        completed=[GameSummary(**g) for g in data["completed"]],
    )


@router.post("", status_code=201, response_model=GameDetail)
async def create_game(
    body: CreateGameRequest,
    user: CurrentUser,
    db: Db,
    request: Request,
    background_tasks: BackgroundTasks,
):
    if body.player_side not in ("red", "blue"):
        raise AppError(400, "bad_request", "player_side must be 'red' or 'blue'")

    bot = await game_q.get_bot(db, body.bot_id)
    if bot is None:
        raise AppError(404, "not_found", "Bot not found")

    # Enforce forced player-side for personas like Team Rocket and Clemont.
    descriptor = get_persona(bot["name"])
    if descriptor.forced_player_side is not None:
        if body.player_side != descriptor.forced_player_side:
            raise AppError(
                400,
                "bad_request",
                f"This opponent requires player_side='{descriptor.forced_player_side}'",
            )

    async with db.transaction():
        roster = await ensure_roster(db, user["id"], body.player_side)
        state = GameState.new_game()
        id_map = build_id_map(roster, body.player_side)
        state_dict = state_to_dict(state, id_map)

        bot_side = "blue" if body.player_side == "red" else "red"
        red_id = user["id"] if body.player_side == "red" else None
        blue_id = user["id"] if body.player_side == "blue" else None

        game = await game_q.insert_game(
            db,
            red_player_id=red_id,
            blue_player_id=blue_id,
            is_bot_game=True,
            bot_id=body.bot_id,
            bot_side=bot_side,
            state_json=json.dumps(state_dict),
        )

        await create_game_pokemon_map(db, game["id"], id_map)

    # Games always start with whose_turn='red'. When the bot is Red, schedule
    # its opening move immediately — otherwise the client sits on the bot's
    # turn until the 15s frontend retry fires.
    if bot_side == "red":
        background_tasks.add_task(_run_bot_move, request.app, game["id"], user["id"])

    return _game_detail(game)


@router.get("/{game_id}", response_model=GameDetail)
async def get_game(game_id: UUID, user: CurrentUser, db: Db):
    game = await game_q.get_game(db, game_id)
    if game is None:
        raise AppError(404, "not_found", "Game not found")
    if not _user_is_participant(game, user["id"]):
        raise AppError(403, "forbidden", "Not a participant in this game")
    return _game_detail(game)


@router.post("/{game_id}/resign", response_model=GameDetail)
async def resign_game(game_id: UUID, user: CurrentUser, db: Db):
    from ..game_logic.xp import compute_xp
    from ..db.queries.game_map import update_xp_earned

    async with db.transaction():
        game = await game_q.get_game_for_move(db, game_id)
        if game is None:
            raise AppError(404, "not_found", "Game not found")
        if not _user_is_participant(game, user["id"]):
            raise AppError(403, "forbidden", "Not a participant in this game")
        if game["status"] != "active":
            raise AppError(409, "game_not_active", "Game is not active")

        if game["red_player_id"] == user["id"]:
            winner = "blue"
        else:
            winner = "red"

        await game_q.set_game_complete(db, game_id, winner, "resign")

        history = game.get("move_history") or []
        if isinstance(history, str):
            history = json.loads(history)
        xp_map = compute_xp(history)
        if xp_map:
            await update_xp_earned(db, game_id, xp_map, winner, "resign")

    updated = await game_q.get_game(db, game_id)
    return _game_detail(updated)
