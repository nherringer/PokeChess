from __future__ import annotations

from uuid import UUID

import asyncpg


async def has_roster(db: asyncpg.Connection, user_id: UUID) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM pokemon_pieces WHERE owner_id = $1 LIMIT 1", user_id
    )
    return row is not None
