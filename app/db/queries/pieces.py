from __future__ import annotations

from uuid import UUID

import asyncpg

# Canonical starter set — one full chess set's worth of Pokémon
_STARTER_PIECES = [
    ("king", "PIKACHU"),
    ("queen", "MEW"),
    ("rook", "SQUIRTLE"),
    ("rook", "SQUIRTLE"),
    ("bishop", "BULBASAUR"),
    ("bishop", "BULBASAUR"),
    ("knight", "CHARMANDER"),
    ("knight", "CHARMANDER"),
]


async def has_roster(db: asyncpg.Connection, user_id: UUID) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM pokemon_pieces WHERE owner_id = $1 LIMIT 1", user_id
    )
    return row is not None


async def insert_starter_pieces(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    """Bulk-insert the starter set and return the created rows."""
    rows = await db.fetch(
        """
        INSERT INTO pokemon_pieces (owner_id, role, species)
        SELECT $1, role, species
        FROM unnest($2::text[], $3::text[]) AS t(role, species)
        RETURNING id, role, species, xp, evolution_stage
        """,
        user_id,
        [p[0] for p in _STARTER_PIECES],
        [p[1] for p in _STARTER_PIECES],
    )
    return [dict(r) for r in rows]


async def get_pieces(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, role, species, xp, evolution_stage FROM pokemon_pieces WHERE owner_id = $1",
        user_id,
    )
    return [dict(r) for r in rows]
