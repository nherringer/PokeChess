from __future__ import annotations

import json
from uuid import UUID

import asyncpg


async def get_bot(db: asyncpg.Connection, bot_id: UUID) -> dict | None:
    row = await db.fetchrow("SELECT id, name, params FROM bots WHERE id = $1", bot_id)
    return dict(row) if row else None


async def insert_game(
    db: asyncpg.Connection,
    *,
    red_player_id: UUID | None,
    blue_player_id: UUID | None,
    is_bot_game: bool,
    bot_id: UUID | None,
    bot_side: str | None,
    state_json: str,
) -> dict:
    row = await db.fetchrow(
        """
        INSERT INTO games (
            red_player_id, blue_player_id,
            is_bot_game, bot_id, bot_side,
            status, whose_turn, turn_number, state
        ) VALUES ($1, $2, $3, $4, $5, 'active', 'red', 1, $6::jsonb)
        RETURNING id, status, whose_turn, turn_number, is_bot_game, bot_side,
                  red_player_id, blue_player_id, winner, end_reason,
                  state, move_history, created_at, updated_at
        """,
        red_player_id,
        blue_player_id,
        is_bot_game,
        bot_id,
        bot_side,
        state_json,
    )
    return dict(row)


async def get_game(db: asyncpg.Connection, game_id: UUID) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT id, status, whose_turn, turn_number, is_bot_game, bot_side, bot_id,
               red_player_id, blue_player_id, winner, end_reason,
               state, move_history, created_at, updated_at
        FROM games WHERE id = $1
        """,
        game_id,
    )
    return dict(row) if row else None


async def get_game_for_move(db: asyncpg.Connection, game_id: UUID) -> dict | None:
    """Fetch game row with all fields needed for move processing.

    Uses SELECT ... FOR UPDATE to prevent concurrent move application.
    Must be called within a transaction.
    """
    row = await db.fetchrow(
        """
        SELECT g.id, g.status, g.whose_turn, g.turn_number,
               g.is_bot_game, g.bot_side, g.bot_id,
               g.red_player_id, g.blue_player_id,
               g.state, g.move_history,
               b.params AS bot_params
        FROM games g
        LEFT JOIN bots b ON b.id = g.bot_id
        WHERE g.id = $1
        FOR UPDATE OF g
        """,
        game_id,
    )
    return dict(row) if row else None


async def list_games_for_user(db: asyncpg.Connection, user_id: UUID) -> dict:
    # opponent_display: other human's username, or bot name for PvB.
    # my_side: 'red' | 'blue' for the requesting user (for turn copy in clients).
    _list_sql = """
        SELECT g.id, g.status, g.whose_turn, g.turn_number, g.is_bot_game, g.bot_side,
               g.red_player_id, g.blue_player_id, g.winner, g.updated_at,
               CASE
                   WHEN g.is_bot_game THEN b.name
                   WHEN g.red_player_id = $1 THEN u_blue.username
                   ELSE u_red.username
               END AS opponent_display,
               CASE
                   WHEN g.red_player_id = $1 THEN 'red'
                   WHEN g.blue_player_id = $1 THEN 'blue'
                   ELSE NULL
               END AS my_side
        FROM games g
        LEFT JOIN users u_red ON u_red.id = g.red_player_id
        LEFT JOIN users u_blue ON u_blue.id = g.blue_player_id
        LEFT JOIN bots b ON b.id = g.bot_id
        WHERE (g.red_player_id = $1 OR g.blue_player_id = $1) AND g.status = $2
        ORDER BY g.updated_at DESC
    """
    active = await db.fetch(
        _list_sql,
        user_id,
        "active",
    )
    completed = await db.fetch(
        _list_sql + "\nLIMIT 10",
        user_id,
        "complete",
    )
    return {
        "active": [dict(r) for r in active],
        "completed": [dict(r) for r in completed],
    }


async def update_game_state(
    db: asyncpg.Connection,
    game_id: UUID,
    *,
    state_json: str,
    new_history_json: str,
    whose_turn: str,
    turn_number: int,
    status: str = "active",
    winner: str | None = None,
    end_reason: str | None = None,
) -> None:
    await db.execute(
        """
        UPDATE games SET
            state = $2::jsonb,
            move_history = move_history || $3::jsonb,
            whose_turn = $4,
            turn_number = $5,
            status = $6,
            winner = $7,
            end_reason = $8,
            updated_at = now()
        WHERE id = $1
        """,
        game_id,
        state_json,
        new_history_json,
        whose_turn,
        turn_number,
        status,
        winner,
        end_reason,
    )


async def set_game_complete(
    db: asyncpg.Connection,
    game_id: UUID,
    winner: str,
    end_reason: str,
) -> None:
    await db.execute(
        """
        UPDATE games SET status = 'complete', winner = $2, end_reason = $3, updated_at = now()
        WHERE id = $1
        """,
        game_id,
        winner,
        end_reason,
    )
