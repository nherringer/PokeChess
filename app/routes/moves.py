from __future__ import annotations

import asyncio
import json
import logging
import random
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Request

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

logger = logging.getLogger(__name__)

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


async def _run_bot_move(app, game_id: UUID, user_id: UUID) -> None:
    """
    Apply the bot's move for game_id using a split-transaction pattern.

    T2a: read game + bot params, record activity, snapshot turn_number; commit.
    Engine HTTP call runs with no DB connection held.
    T2b: re-lock game, re-validate against the T2a snapshot, apply bot move,
         update row, compute XP; commit.

    Splitting the transaction means the engine call (up to ~25s worst case)
    never holds a DB connection or a FOR UPDATE lock on the game row. The
    T2b re-validation handles the states that can change during the engine
    call (resign, concurrent _run_bot_move application).

    Idempotent: any exit path logs and returns. Expected at low volume under
    the retry endpoint — not an error condition.
    """
    from ..engine_client import call_bot_move
    from ..db.queries.bot_activity import count_active_bot_players, upsert_player_activity
    from .. import config

    pool = app.state.db_pool

    # ----- T2a: read state, record activity, snapshot for re-validation -----
    try:
        async with pool.acquire() as db:
            async with db.transaction():
                game = await game_q.get_game_for_move(db, game_id)
                if game is None:
                    logger.info("Bot move skipped (T2a): game %s not found", game_id)
                    return
                if game["status"] != "active":
                    logger.info(
                        "Bot move skipped (T2a): game %s status=%s",
                        game_id, game["status"],
                    )
                    return
                if not game["is_bot_game"] or game["whose_turn"] != game["bot_side"]:
                    logger.info(
                        "Bot move skipped (T2a): game %s not awaiting bot "
                        "(is_bot_game=%s, whose_turn=%s, bot_side=%s)",
                        game_id, game["is_bot_game"],
                        game["whose_turn"], game.get("bot_side"),
                    )
                    return

                bot_id = game["bot_id"]
                bot_params = game.get("bot_params") or {}
                # asyncpg returns JSONB as a string unless a codec is registered;
                # decode before reading params so the 3.0s fallback doesn't hide
                # per-persona settings like Bonnie's time_budget=0.1.
                if isinstance(bot_params, str):
                    bot_params = json.loads(bot_params)
                if not isinstance(bot_params, dict):
                    bot_params = {}
                base_time_budget = float(bot_params.get("time_budget", 3.0))

                # Record this player's move before counting so they're included in N.
                await upsert_player_activity(db, user_id, bot_id)

                n_active = await count_active_bot_players(
                    db, bot_id, config.BOT_ACTIVE_WINDOW_MINUTES
                )
                effective_time_budget = base_time_budget / n_active
                persona_params = {**bot_params, "time_budget": effective_time_budget}

                state_data = game["state"]
                if isinstance(state_data, str):
                    state_data = json.loads(state_data)
                state, id_map = state_from_dict(state_data)

                bot_state_dict = state_to_dict(state, id_map)
                expected_turn_number = game["turn_number"]
                expected_bot_side = game["bot_side"]
    except Exception:
        logger.exception("Bot move T2a failed for game %s", game_id)
        return

    # ----- Engine call: no DB connection held -----
    try:
        bot_move_raw = await call_bot_move(
            app.state.engine_client, bot_state_dict, persona_params
        )
    except Exception:
        logger.exception("Engine call failed for game %s", game_id)
        return

    # ----- T2b: re-validate against T2a snapshot, then apply -----
    # TRADE and other "free" actions keep whose_turn with the bot. Track whether
    # we need to re-queue ourselves after the transaction commits.
    continue_bot = False
    try:
        async with pool.acquire() as db:
            async with db.transaction():
                game2 = await game_q.get_game_for_move(db, game_id)
                if game2 is None:
                    logger.warning(
                        "Bot move dropped (T2b): game %s disappeared after engine call",
                        game_id,
                    )
                    return
                if game2["status"] != "active":
                    logger.info(
                        "Bot move dropped (T2b): game %s status changed to %s "
                        "during engine call",
                        game_id, game2["status"],
                    )
                    return
                if game2["whose_turn"] != expected_bot_side:
                    logger.warning(
                        "Bot move dropped (T2b): game %s whose_turn=%s (expected %s)",
                        game_id, game2["whose_turn"], expected_bot_side,
                    )
                    return
                if game2["turn_number"] != expected_turn_number:
                    logger.warning(
                        "Bot move dropped (T2b): game %s turn_number=%d "
                        "(expected %d; concurrent application)",
                        game_id, game2["turn_number"], expected_turn_number,
                    )
                    return

                state_data2 = game2["state"]
                if isinstance(state_data2, str):
                    state_data2 = json.loads(state_data2)
                state2, id_map2 = state_from_dict(state_data2)

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
                except (KeyError, TypeError) as exc:
                    logger.error("Bot move parse error for game %s: %s", game_id, exc)
                    return

                bot_legal = get_legal_moves(state2)
                if not any(_moves_equal(bot_move, lm) for lm in bot_legal):
                    logger.error("Engine returned illegal move for game %s", game_id)
                    return

                new_state, id_map2, bot_entries, done, winner_side = _apply_and_record(
                    state2, bot_move, id_map2,
                )

                final_status = "complete" if done else "active"
                final_whose_turn = new_state.active_player.name.lower()
                final_turn = new_state.turn_number
                end_reason = None
                if done:
                    end_reason = "draw" if winner_side == "draw" else "king_eliminated"

                final_state_dict = state_to_dict(new_state, id_map2)

                await game_q.update_game_state(
                    db,
                    game_id,
                    state_json=json.dumps(final_state_dict),
                    new_history_json=json.dumps(bot_entries),
                    whose_turn=final_whose_turn,
                    turn_number=final_turn,
                    status=final_status,
                    winner=winner_side if done and winner_side != "draw" else None,
                    end_reason=end_reason,
                )

                if done:
                    full_history = game2.get("move_history") or []
                    if isinstance(full_history, str):
                        full_history = json.loads(full_history)
                    full_history.extend(bot_entries)
                    xp_map = compute_xp(full_history)
                    if xp_map:
                        await update_xp_earned(
                            db, game_id, xp_map,
                            winner_side if winner_side != "draw" else None,
                            end_reason,
                        )
                elif final_whose_turn == expected_bot_side:
                    continue_bot = True
    except Exception:
        logger.exception("Bot move T2b failed for game %s", game_id)
        return

    if continue_bot:
        # Schedule the follow-up as a detached task so this coroutine returns
        # promptly (letting BackgroundTasks release its slot) and the new call
        # starts its own T2a snapshot. _run_bot_move is idempotent, so a spurious
        # schedule (e.g. the human already moved in parallel) is a no-op.
        asyncio.create_task(_run_bot_move(app, game_id, user_id))


@router.post("/{game_id}/move", response_model=GameDetail)
async def submit_move(
    game_id: UUID,
    body: MovePayload,
    user: CurrentUser,
    db: Db,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Track whether a bot move needs to be scheduled after the transaction commits.
    bot_move_needed = False

    async with db.transaction():
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

        try:
            move = _parse_move(body)
        except KeyError:
            raise AppError(400, "bad_request", f"Invalid action_type: {body.action_type}")

        state_data = game["state"]
        if isinstance(state_data, str):
            state_data = json.loads(state_data)
        state, id_map = state_from_dict(state_data)

        legal = get_legal_moves(state)
        if not any(_moves_equal(move, lm) for lm in legal):
            raise AppError(400, "illegal_move", "Move is not legal in current state")

        # Apply human move only.
        all_history = []
        new_state, id_map, entries, done, winner_side = _apply_and_record(state, move, id_map)
        all_history.extend(entries)

        final_status = "complete" if done else "active"
        final_whose_turn = new_state.active_player.name.lower()
        final_turn = new_state.turn_number
        end_reason = None
        if done:
            end_reason = "draw" if winner_side == "draw" else "king_eliminated"

        final_state_dict = state_to_dict(new_state, id_map)

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

        if not done and game["is_bot_game"] and game["bot_side"] == final_whose_turn:
            bot_move_needed = True

    # Schedule bot move outside the transaction so T1 is committed before the
    # engine call begins.  The background task re-acquires its own connection
    # and transaction, and is idempotent.
    if bot_move_needed:
        background_tasks.add_task(_run_bot_move, request.app, game_id, user["id"])

    # Fetch updated game for response (read committed — reflects human move).
    updated = await game_q.get_game(db, game_id)
    return _game_detail(updated)


@router.post("/{game_id}/retry-bot-move", status_code=202)
async def retry_bot_move(
    game_id: UUID,
    user: CurrentUser,
    db: Db,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Re-queue the bot move for a game stuck with whose_turn == bot_side.

    Called automatically by the frontend after ~15 seconds if the bot move
    hasn't arrived via polling.  Idempotent: _run_bot_move exits silently if
    it's no longer the bot's turn.
    """
    game = await game_q.get_game(db, game_id)
    if game is None:
        raise AppError(404, "not_found", "Game not found")

    team = _player_team(game, user["id"])
    if team is None:
        raise AppError(403, "forbidden", "Not a participant in this game")

    if game["status"] != "active":
        raise AppError(409, "game_not_active", "Game is not active")

    if not game["is_bot_game"]:
        raise AppError(409, "not_bot_game", "Not a bot game")

    if game["whose_turn"] != game["bot_side"]:
        raise AppError(409, "not_bot_turn", "It is not the bot's turn")

    background_tasks.add_task(_run_bot_move, request.app, game_id, user["id"])
    return {"status": "queued"}
