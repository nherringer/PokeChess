from __future__ import annotations

import random
from uuid import UUID

import asyncpg


async def has_pending_invite_between(
    db: asyncpg.Connection, user_a: UUID, user_b: UUID
) -> bool:
    """True if either direction has a pending invite between the two users."""
    row = await db.fetchrow(
        """
        SELECT 1 FROM game_invites
        WHERE status = 'pending'
          AND (
            (inviter_id = $1 AND invitee_id = $2)
            OR (inviter_id = $2 AND invitee_id = $1)
          )
        LIMIT 1
        """,
        user_a,
        user_b,
    )
    return row is not None


async def get_pending_invites(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    """Pending game invites where the user is invitee (incoming) or inviter (outgoing)."""
    rows = await db.fetch(
        """
        SELECT * FROM (
            SELECT gi.id, g.id AS game_id, gi.created_at,
                   'incoming'::text AS direction,
                   gi.inviter_id AS other_user_id,
                   gi.inviter_id, gi.invitee_id,
                   gi.inviter_side,
                   u.username AS other_username
            FROM game_invites gi
            JOIN users u ON u.id = gi.inviter_id
            JOIN games g ON g.invite_id = gi.id
            WHERE gi.invitee_id = $1 AND gi.status = 'pending'
            UNION ALL
            SELECT gi.id, g.id AS game_id, gi.created_at,
                   'outgoing'::text AS direction,
                   gi.invitee_id AS other_user_id,
                   gi.inviter_id, gi.invitee_id,
                   gi.inviter_side,
                   u.username AS other_username
            FROM game_invites gi
            JOIN users u ON u.id = gi.invitee_id
            JOIN games g ON g.invite_id = gi.id
            WHERE gi.inviter_id = $1 AND gi.status = 'pending'
        ) AS combined
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_invite(db: asyncpg.Connection, invite_id: UUID) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT gi.id, gi.inviter_id, gi.invitee_id, gi.status,
               gi.inviter_side, g.id AS game_id,
               g.red_player_id, g.blue_player_id
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
    inviter_side: str,
) -> dict:
    """Create invite + pending game row in one transaction.

    inviter_side must be 'red', 'blue', or 'random'.
    'random' is resolved to a concrete side here before writing to the DB.
    """
    if inviter_side == "random":
        inviter_side = random.choice(["red", "blue"])

    red_id  = inviter_id if inviter_side == "red" else invitee_id
    blue_id = invitee_id if inviter_side == "red" else inviter_id

    async with db.transaction():
        invite = await db.fetchrow(
            """
            INSERT INTO game_invites (inviter_id, invitee_id, inviter_side)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            inviter_id,
            invitee_id,
            inviter_side,
        )
        game = await db.fetchrow(
            """
            INSERT INTO games (
                red_player_id, blue_player_id,
                is_bot_game, invite_id, status
            ) VALUES ($1, $2, false, $3, 'pending')
            RETURNING id
            """,
            red_id,
            blue_id,
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
