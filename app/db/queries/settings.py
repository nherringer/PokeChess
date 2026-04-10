from __future__ import annotations

import json
from uuid import UUID

import asyncpg


async def create_default_settings(db: asyncpg.Connection, user_id: UUID) -> None:
    await db.execute(
        "INSERT INTO user_settings (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
        user_id,
    )


async def get_settings(db: asyncpg.Connection, user_id: UUID) -> dict | None:
    row = await db.fetchrow(
        "SELECT board_theme, extra_settings, updated_at FROM user_settings WHERE user_id = $1",
        user_id,
    )
    return dict(row) if row else None


async def update_settings(
    db: asyncpg.Connection,
    user_id: UUID,
    board_theme: str | None,
    extra_settings: dict | None,
) -> dict:
    row = await db.fetchrow(
        """
        UPDATE user_settings SET
            board_theme    = COALESCE($2, board_theme),
            extra_settings = CASE WHEN $3::text IS NOT NULL
                             THEN extra_settings || $3::jsonb
                             ELSE extra_settings END,
            updated_at     = now()
        WHERE user_id = $1
        RETURNING board_theme, extra_settings, updated_at
        """,
        user_id,
        board_theme,
        json.dumps(extra_settings) if extra_settings is not None else None,
    )
    return dict(row)
