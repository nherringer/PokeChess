from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_pending_invites(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT gi.id, gi.inviter_id AS from_user_id, u.username AS from_username,
               g.id AS game_id, gi.created_at
        FROM game_invites gi
        JOIN users u ON u.id = gi.inviter_id
        JOIN games g ON g.invite_id = gi.id
        WHERE gi.invitee_id = $1 AND gi.status = 'pending'
        ORDER BY gi.created_at DESC
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_invite(db: asyncpg.Connection, invite_id: UUID) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT gi.id, gi.inviter_id, gi.invitee_id, gi.status,
               g.id AS game_id
        FROM game_invites gi
        JOIN games g ON g.invite_id = gi.id
        WHERE gi.id = $1
        """,
        invite_id,
    )
    return dict(row) if row else None


async def insert_invite_and_game(
    db: asyncpg.Connection,
    inviter_id: UUID,
    invitee_id: UUID,
) -> dict:
    """Create invite + pending game row in one transaction."""
    async with db.transaction():
        invite = await db.fetchrow(
            """
            INSERT INTO game_invites (inviter_id, invitee_id)
            VALUES ($1, $2)
            RETURNING id
            """,
            inviter_id,
            invitee_id,
        )
        game = await db.fetchrow(
            """
            INSERT INTO games (
                red_player_id, blue_player_id,
                is_bot_game, invite_id, status
            ) VALUES ($1, $2, false, $3, 'pending')
            RETURNING id
            """,
            inviter_id,
            invitee_id,
            invite["id"],
        )
    return {"invite_id": invite["id"], "game_id": game["id"], "status": "pending"}


async def update_invite_status(
    db: asyncpg.Connection, invite_id: UUID, status: str
) -> None:
    await db.execute(
        "UPDATE game_invites SET status = $2 WHERE id = $1",
        invite_id,
        status,
    )
