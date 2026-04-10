"""
Queries for the bot_player_activity table.

Used by the move handler to implement load-aware MCTS budget scaling:
the effective time_budget sent to the engine is divided by the number of
players currently active against the same bot personality.

See docs/load_aware_budgeting.md for design details.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def upsert_player_activity(
    db: asyncpg.Connection,
    player_id: UUID,
    bot_id: UUID,
) -> None:
    """Record (or refresh) that player_id just moved in a game against bot_id."""
    await db.execute(
        """
        INSERT INTO bot_player_activity (player_id, bot_id, last_moved_at)
        VALUES ($1, $2, now())
        ON CONFLICT (player_id, bot_id) DO UPDATE SET last_moved_at = now()
        """,
        player_id,
        bot_id,
    )


async def count_active_bot_players(
    db: asyncpg.Connection,
    bot_id: UUID,
    window_minutes: int,
) -> int:
    """
    Count distinct players who have moved against bot_id in the last
    window_minutes minutes.  Always returns at least 1 (the current caller
    will have been upserted before this query runs).
    """
    row = await db.fetchrow(
        """
        SELECT COUNT(*) AS n
        FROM bot_player_activity
        WHERE bot_id = $1
          AND last_moved_at > now() - ($2 * interval '1 minute')
        """,
        bot_id,
        window_minutes,
    )
    return max(1, int(row["n"]) if row else 0)
