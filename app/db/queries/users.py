from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_user_by_email(db: asyncpg.Connection, email: str) -> dict | None:
    row = await db.fetchrow(
        "SELECT id, username, email, password_hash, created_at FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_email_public(db: asyncpg.Connection, email: str) -> dict | None:
    """Like get_user_by_email but omits password_hash — for non-auth contexts."""
    row = await db.fetchrow(
        "SELECT id, username, email, created_at FROM users WHERE email = $1",
        email,
    )
    return dict(row) if row else None


async def get_user_by_username(db: asyncpg.Connection, username: str) -> dict | None:
    row = await db.fetchrow(
        "SELECT id, username, email, created_at FROM users WHERE username = $1",
        username,
    )
    return dict(row) if row else None


async def insert_user(
    db: asyncpg.Connection, username: str, email: str, password_hash: str
) -> dict:
    row = await db.fetchrow(
        """
        INSERT INTO users (username, email, password_hash)
        VALUES ($1, $2, $3)
        RETURNING id, username, email, created_at
        """,
        username,
        email,
        password_hash,
    )
    return dict(row)


async def get_user_pieces(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT id, role, species, set_side, xp, evolution_stage
        FROM pokemon_pieces
        WHERE owner_id = $1
        ORDER BY set_side, created_at
        """,
        user_id,
    )
    return [dict(r) for r in rows]
