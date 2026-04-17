from __future__ import annotations

from uuid import UUID

import asyncpg

# Two full chess sets — one red (Pikachu king), one blue (Eevee king).
_RED_STARTER_PIECES = [
    ("king",   "PIKACHU",    "red"),
    ("queen",  "MEW",        "red"),
    ("rook",   "SQUIRTLE",   "red"),
    ("rook",   "SQUIRTLE",   "red"),
    ("bishop", "BULBASAUR",  "red"),
    ("bishop", "BULBASAUR",  "red"),
    ("knight", "CHARMANDER", "red"),
    ("knight", "CHARMANDER", "red"),
]

_BLUE_STARTER_PIECES = [
    ("king",   "EEVEE",      "blue"),
    ("queen",  "MEW",        "blue"),
    ("rook",   "SQUIRTLE",   "blue"),
    ("rook",   "SQUIRTLE",   "blue"),
    ("bishop", "BULBASAUR",  "blue"),
    ("bishop", "BULBASAUR",  "blue"),
    ("knight", "CHARMANDER", "blue"),
    ("knight", "CHARMANDER", "blue"),
]

_ALL_STARTER_PIECES = _RED_STARTER_PIECES + _BLUE_STARTER_PIECES


async def has_roster(db: asyncpg.Connection, user_id: UUID) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM pokemon_pieces WHERE owner_id = $1 LIMIT 1", user_id
    )
    return row is not None


async def insert_starter_pieces(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    """Bulk-insert both red and blue starter sets (16 pieces) and return created rows."""
    rows = await db.fetch(
        """
        INSERT INTO pokemon_pieces (owner_id, role, species, set_side)
        SELECT $1, role, species, set_side
        FROM unnest($2::text[], $3::text[], $4::text[]) AS t(role, species, set_side)
        RETURNING id, role, species, set_side, xp, evolution_stage
        """,
        user_id,
        [p[0] for p in _ALL_STARTER_PIECES],
        [p[1] for p in _ALL_STARTER_PIECES],
        [p[2] for p in _ALL_STARTER_PIECES],
    )
    return [dict(r) for r in rows]


async def get_pieces(db: asyncpg.Connection, user_id: UUID) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, role, species, set_side, xp, evolution_stage FROM pokemon_pieces WHERE owner_id = $1",
        user_id,
    )
    return [dict(r) for r in rows]
