from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_friends_and_requests(db: asyncpg.Connection, user_id: UUID) -> dict:
    """Return accepted friends, incoming pending, and outgoing pending in one pass."""
    rows = await db.fetch(
        """
        SELECT
            f.id,
            f.user_a_id,
            f.user_b_id,
            f.initiator_id,
            f.status,
            ua.username AS a_username,
            ub.username AS b_username
        FROM friendships f
        JOIN users ua ON ua.id = f.user_a_id
        JOIN users ub ON ub.id = f.user_b_id
        WHERE (f.user_a_id = $1 OR f.user_b_id = $1)
          AND f.status IN ('pending', 'accepted')
        """,
        user_id,
    )
    friends, incoming, outgoing = [], [], []
    for r in rows:
        other_id = r["user_b_id"] if r["user_a_id"] == user_id else r["user_a_id"]
        other_name = r["b_username"] if r["user_a_id"] == user_id else r["a_username"]

        if r["status"] == "accepted":
            friends.append({"user_id": other_id, "username": other_name})
        elif r["initiator_id"] == user_id:
            outgoing.append({"id": r["id"], "to_user_id": other_id, "username": other_name})
        else:
            incoming.append({"id": r["id"], "from_user_id": r["initiator_id"], "username": other_name})

    return {"friends": friends, "incoming": incoming, "outgoing": outgoing}


async def insert_friendship(
    db: asyncpg.Connection, user_a_id: UUID, user_b_id: UUID, initiator_id: UUID
) -> dict:
    # Enforce ordering: user_a_id < user_b_id
    a, b = sorted([user_a_id, user_b_id], key=str)
    row = await db.fetchrow(
        """
        INSERT INTO friendships (user_a_id, user_b_id, initiator_id, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING id, status
        """,
        a,
        b,
        initiator_id,
    )
    return dict(row)


async def get_friendship(db: asyncpg.Connection, friendship_id: UUID) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT id, user_a_id, user_b_id, initiator_id, status
        FROM friendships WHERE id = $1
        """,
        friendship_id,
    )
    return dict(row) if row else None


async def update_friendship_status(
    db: asyncpg.Connection, friendship_id: UUID, status: str
) -> dict:
    row = await db.fetchrow(
        "UPDATE friendships SET status = $2 WHERE id = $1 RETURNING id, status",
        friendship_id,
        status,
    )
    return dict(row)


async def are_friends(db: asyncpg.Connection, user1: UUID, user2: UUID) -> bool:
    a, b = sorted([user1, user2], key=str)
    row = await db.fetchrow(
        """
        SELECT 1 FROM friendships
        WHERE user_a_id = $1 AND user_b_id = $2 AND status = 'accepted'
        """,
        a,
        b,
    )
    return row is not None
