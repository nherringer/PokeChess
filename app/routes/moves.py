from __future__ import annotations

import json
import random
from uuid import UUID

from fastapi import APIRouter, Query, Request

from engine.moves import get_legal_moves, ActionType, Move
from engine.rules import apply_move, is_terminal
from engine.state import PieceType, Team

from ..auth import Db, CurrentUser
from ..main import AppError
from ..schemas import GameDetail, LegalMoveOut, MovePayload
from ..game_logic.serialization import state_from_dict, state_to_dict, IdMap
from ..game_logic.id_map import remap_ids
from ..game_logic.history import build_history_entry, build_foresight_resolve_entry
from ..game_logic.xp import compute_xp
from ..db.queries import games as game_q
from ..db.queries.game_map import update_xp_earned

router = APIRouter(prefix="/games", tags=["moves"])


def _player_team(game: dict, user_id: UUID) -> Team | None:
    if game.get("red_player_id") == user_id:
        return Team.RED
    if game.get("blue_player_id") == user_id:
        return Team.BLUE
    return None


def _move_to_out(m: Move) -> LegalMoveOut:
    return LegalMoveOut(
        piece_row=m.piece_row,
        piece_col=m.piece_col,
        action_type=m.action_type.name,
        target_row=m.target_row,
        target_col=m.target_col,
        secondary_row=m.secondary_row,
        secondary_col=m.secondary_col,
        move_slot=m.move_slot,
    )


def _game_detail(game: dict) -> GameDetail:
    state = game.get("state")
    history = game.get("move_history")
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


def _parse_move(payload: MovePayload) -> Move:
    """Convert a MovePayload (API schema) into an engine Move object."""
    return Move(
        piece_row=payload.piece_row,
        piece_col=payload.piece_col,
        action_type=ActionType[payload.action_type],
        target_row=payload.target_row,
        target_col=payload.target_col,
        secondary_row=payload.secondary_row,
        secondary_col=payload.secondary_col,
        move_slot=payload.move_slot,
    )


def _moves_equal(a: Move, b: Move) -> bool:
    return (
        a.piece_row == b.piece_row
        and a.piece_col == b.piece_col
        and a.action_type == b.action_type
        and a.target_row == b.target_row
        and a.target_col == b.target_col
        and a.secondary_row == b.secondary_row
        and a.secondary_col == b.secondary_col
        and a.move_slot == b.move_slot
    )


def _detect_foresight_resolve(old_state, id_map: IdMap) -> dict | None:
    """If foresight resolved inside apply_move, build the history entry."""
    player = old_state.active_player
    fx = old_state.pending_foresight.get(player)
    if fx is None:
        return None
    if fx.resolves_on_turn != old_state.turn_number:
        return None
    return build_foresight_resolve_entry(old_state, fx, id_map)


def _apply_and_record(
    old_state, move: Move, id_map: IdMap,
) -> tuple:
    """
    Apply a move, resolve RNG, remap IDs, build history entries.

    Returns (new_state, new_id_map, history_entries, done, winner_side).
    """
    history_entries = []

    # Check for foresight resolution (happens at start of apply_move)
    fx_entry = _detect_foresight_resolve(old_state, id_map)
    if fx_entry is not None:
        history_entries.append(fx_entry)

    # Apply the move
    outcomes = apply_move(old_state, move)

    piece_moving = old_state.board[move.piece_row][move.piece_col]
    is_pokeball_attack = (
        move.action_type == ActionType.ATTACK
        and piece_moving is not None
        and piece_moving.piece_type == PieceType.POKEBALL
    )

    # Resolve RNG for pokeball (engine: stochastic capture is exactly two outcomes)
    rng_roll = None
    captured = None
    if len(outcomes) == 2:
        if not is_pokeball_attack:
            raise AppError(500, "internal_error", "Unexpected stochastic outcomes from engine")
        rng_roll = random.random()
        if rng_roll < outcomes[0][1]:
            new_state = outcomes[0][0]
            captured = True
        else:
            new_state = outcomes[1][0]
            captured = False
    elif len(outcomes) == 1:
        new_state = outcomes[0][0]
        if is_pokeball_attack:
            rng_roll = None
            captured = False
    else:
        raise AppError(500, "internal_error", "Invalid outcome list from engine")

    # Build the move's history entry (using old_state for damage calc)
    move_entry = build_history_entry(
        old_state, new_state, move, id_map,
        rng_roll=rng_roll, captured=captured,
    )
    history_entries.append(move_entry)

    # Remap IDs
    new_id_map = remap_ids(old_state, new_state, move, id_map)

    # Check terminal
    done, winner = is_terminal(new_state)
    winner_side = None
    if done and winner is not None:
        winner_side = winner.name.lower()
    elif done:
        winner_side = "draw"

    return new_state, new_id_map, history_entries, done, winner_side


@router.get("/{game_id}/legal_moves", response_model=list[LegalMoveOut])
async def legal_moves(
    game_id: UUID,
    user: CurrentUser,
    db: Db,
    piece_row: int = Query(..., ge=0, le=7),
    piece_col: int = Query(..., ge=0, le=7),
):
    game = await game_q.get_game(db, game_id)
    if game is None:
        raise AppError(404, "not_found", "Game not found")

    team = _player_team(game, user["id"])
    if team is None:
        raise AppError(403, "forbidden", "Not a participant in this game")

    if game["status"] != "active":
        raise AppError(409, "game_not_active", "Game is not active")

    if game["whose_turn"] != team.name.lower():
        raise AppError(409, "not_your_turn", "It is not your turn")

    state_data = game["state"]
    if isinstance(state_data, str):
        state_data = json.loads(state_data)

    state, _id_map = state_from_dict(state_data)

    # Validate piece exists and belongs to active player
    piece = state.board[piece_row][piece_col]
    if piece is None or piece.team != team:
        raise AppError(400, "bad_request", "No friendly piece at that position")

    all_moves = get_legal_moves(state)
    filtered = [
        _move_to_out(m)
        for m in all_moves
        if m.piece_row == piece_row and m.piece_col == piece_col
    ]
    return filtered


@router.post("/{game_id}/move", response_model=GameDetail)
async def submit_move(
    game_id: UUID,
    body: MovePayload,
    user: CurrentUser,
    db: Db,
    request: Request,
):
    async with db.transaction():
        # FOR UPDATE lock prevents concurrent move application
        game = await game_q.get_game_for_move(db, game_id)
        if game is None:
            raise AppError(404, "not_found", "Game not found")

        team = _player_team(game, user["id"])
        if team is None:
            raise AppError(403, "forbidden", "Not a participant in this game")

        if game["status"] != "active":
            raise AppError(409, "game_not_active", "Game is not active")

        if game["whose_turn"] != team.name.lower():
            raise AppError(409, "not_your_turn", "It is not your turn")

        # Parse the submitted move
        try:
            move = _parse_move(body)
        except KeyError:
            raise AppError(400, "bad_request", f"Invalid action_type: {body.action_type}")

        # Deserialize state
        state_data = game["state"]
        if isinstance(state_data, str):
            state_data = json.loads(state_data)
        state, id_map = state_from_dict(state_data)

        # Validate move is legal
        legal = get_legal_moves(state)
        if not any(_moves_equal(move, lm) for lm in legal):
            raise AppError(400, "illegal_move", "Move is not legal in current state")

        # Apply human move
        all_history = []
        new_state, id_map, entries, done, winner_side = _apply_and_record(state, move, id_map)
        all_history.extend(entries)

        # PvB: if game is not over and it's now the bot's turn, get and apply bot move
        if not done and game["is_bot_game"] and game["bot_side"] == new_state.active_player.name.lower():
            from ..engine_client import request_bot_move

            bot_params = game.get("bot_params") or {}
            time_budget = bot_params.get("time_budget", 3.0) if isinstance(bot_params, dict) else 3.0

            bot_state_dict = state_to_dict(new_state, id_map)
            bot_move_raw = await request_bot_move(request, bot_state_dict, time_budget)

            try:
                bot_move = Move(
                    piece_row=bot_move_raw["piece_row"],
                    piece_col=bot_move_raw["piece_col"],
                    action_type=ActionType[bot_move_raw["action_type"]],
                    target_row=bot_move_raw["target_row"],
                    target_col=bot_move_raw["target_col"],
                    secondary_row=bot_move_raw.get("secondary_row"),
                    secondary_col=bot_move_raw.get("secondary_col"),
                    move_slot=bot_move_raw.get("move_slot"),
                )
            except (KeyError, TypeError):
                raise AppError(503, "engine_error", "Engine returned an invalid move")

            bot_legal = get_legal_moves(new_state)
            if not any(_moves_equal(bot_move, lm) for lm in bot_legal):
                raise AppError(503, "engine_error", "Engine returned an illegal move")

            new_state, id_map, bot_entries, done, winner_side = _apply_and_record(
                new_state, bot_move, id_map,
            )
            all_history.extend(bot_entries)

        # Determine final game status
        final_status = "complete" if done else "active"
        final_whose_turn = new_state.active_player.name.lower()
        final_turn = new_state.turn_number
        end_reason = None
        if done:
            end_reason = "draw" if winner_side == "draw" else "king_eliminated"

        # Serialize final state
        final_state_dict = state_to_dict(new_state, id_map)

        # Persist state + XP atomically within the same transaction
        await game_q.update_game_state(
            db,
            game_id,
            state_json=json.dumps(final_state_dict),
            new_history_json=json.dumps(all_history),
            whose_turn=final_whose_turn,
            turn_number=final_turn,
            status=final_status,
            winner=winner_side if done and winner_side != "draw" else None,
            end_reason=end_reason,
        )

        # On game completion: process XP (inside same transaction)
        if done:
            full_history = game.get("move_history") or []
            if isinstance(full_history, str):
                full_history = json.loads(full_history)
            full_history.extend(all_history)
            xp_map = compute_xp(full_history)
            if xp_map:
                await update_xp_earned(
                    db, game_id, xp_map,
                    winner_side if winner_side != "draw" else None,
                    end_reason,
                )

    # Fetch updated game for response (outside transaction — read committed)
    updated = await game_q.get_game(db, game_id)
    return _game_detail(updated)
