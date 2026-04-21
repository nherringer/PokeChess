"""
Roster creation and piece-UUID injection for new games.

Each user's persistent roster (pokemon_pieces table):
  16 pieces total — 8 red (Pikachu king) + 8 blue (Eevee king).
  Each set: 1 king, 1 queen, 2 rooks, 2 knights, 2 bishops.

UUIDs are injected into the starting board's named pieces;
pawns (pokeball/safetyball) get id=None.
"""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from engine.state import GameState, Team

from .serialization import IdMap, state_to_dict


# Back-rank layout: col → role. Both sides share the same layout; the king at
# col 4 is placed separately so the caller can pick PIKACHU (red) vs EEVEE
# (blue). Mirrors `_place_starting_pieces()` in engine/state.py — see that
# function for which species lands on each square.
_BACK_RANK_LAYOUT: dict[int, str] = {
    0: "rook",
    1: "knight",
    2: "bishop",
    3: "queen",
    # 4: king — placed separately by side
    5: "bishop",
    6: "knight",
    7: "rook",
}

# Both rosters: (set_side, role, species). Red set first, blue set second.
# Species casing matches `insert_starter_pieces` in app/db/queries/pieces.py so
# any user seeded via either path has consistent species strings.
_BOTH_ROSTERS = [
    ("red",  "king",   "PIKACHU"),
    ("red",  "queen",  "MEW"),
    ("red",  "rook",   "SQUIRTLE"),
    ("red",  "rook",   "SQUIRTLE"),
    ("red",  "knight", "CHARMANDER"),
    ("red",  "knight", "CHARMANDER"),
    ("red",  "bishop", "BULBASAUR"),
    ("red",  "bishop", "BULBASAUR"),
    ("blue", "king",   "EEVEE"),
    ("blue", "queen",  "MEW"),
    ("blue", "rook",   "SQUIRTLE"),
    ("blue", "rook",   "SQUIRTLE"),
    ("blue", "knight", "CHARMANDER"),
    ("blue", "knight", "CHARMANDER"),
    ("blue", "bishop", "BULBASAUR"),
    ("blue", "bishop", "BULBASAUR"),
]


async def ensure_roster(db: asyncpg.Connection, user_id: UUID, side: str) -> list[dict]:
    """Return the 8-piece set for the given side, creating it if missing.

    Only the requested side is inserted so that a user already holding the other
    side's pieces does not end up with duplicates.

    Caller must be inside a transaction. The FOR UPDATE on the users row serialises
    concurrent first-seed calls so only one inserts the 8-piece set.
    """
    await db.fetchrow("SELECT id FROM users WHERE id = $1 FOR UPDATE", user_id)
    existing = await db.fetch(
        "SELECT id, role, species FROM pokemon_pieces WHERE owner_id = $1 AND set_side = $2 ORDER BY created_at",
        user_id, side,
    )
    if existing:
        return [dict(r) for r in existing]

    side_pieces = []
    for set_color, role, species in _BOTH_ROSTERS:
        if set_color != side:
            continue
        row = await db.fetchrow(
            """
            INSERT INTO pokemon_pieces (owner_id, role, species, set_side)
            VALUES ($1, $2, $3, $4)
            RETURNING id, role, species
            """,
            user_id, role, species, side,
        )
        side_pieces.append(dict(row))
    return side_pieces


def build_id_map(roster: list[dict], side: str) -> IdMap:
    """
    Map each roster piece to its starting board position.

    The roster has 8 pieces. We assign them to back-rank positions by role,
    left-to-right for duplicates (sorted by creation order = insert order).
    """
    back_row = 0 if side == "red" else 7

    # Group roster pieces by role
    by_role: dict[str, list[dict]] = {}
    for p in roster:
        by_role.setdefault(p["role"], []).append(p)

    id_map: IdMap = {}

    # King at col 4
    kings = by_role.get("king", [])
    if kings:
        id_map[(back_row, 4)] = str(kings[0]["id"])

    # Non-king named pieces from the layout
    for col, role in _BACK_RANK_LAYOUT.items():
        pieces = by_role.get(role, [])
        if not pieces:
            continue
        # Pop first available piece of this role
        piece = pieces.pop(0)
        id_map[(back_row, col)] = str(piece["id"])

    return id_map


async def create_game_pokemon_map(
    db: asyncpg.Connection, game_id: UUID, id_map: IdMap
) -> None:
    """Insert game_pokemon_map rows for all tracked pieces."""
    for pos, piece_id in id_map.items():
        # Skip stored-piece entries (keyed by ("stored", (row, col)))
        if not isinstance(pos, tuple) or not isinstance(pos[0], int):
            continue
        if piece_id is None:
            continue
        await db.execute(
            """
            INSERT INTO game_pokemon_map (game_id, pokemon_piece_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            game_id,
            UUID(piece_id),
        )


async def initialize_pvp_game(
    db: asyncpg.Connection,
    game_id: UUID,
    red_player_id: UUID,
    blue_player_id: UUID,
) -> None:
    """
    Called when a PvP invite is accepted. Builds initial state, injects piece UUIDs,
    writes state to the games row, creates game_pokemon_map entries.

    red_player_id and blue_player_id are read from the game row (set correctly at
    invite-creation time based on the inviter's chosen side). Do not derive them
    from inviter/invitee ordering — that ordering is no longer meaningful.

    Caller must wrap this in a transaction.
    """
    red_roster = await ensure_roster(db, red_player_id, "red")
    blue_roster = await ensure_roster(db, blue_player_id, "blue")

    state = GameState.new_game()
    id_map: IdMap = {}
    id_map.update(build_id_map(red_roster, "red"))
    id_map.update(build_id_map(blue_roster, "blue"))

    state_dict = state_to_dict(state, id_map)

    await db.execute(
        """
        UPDATE games SET
            status = 'active',
            whose_turn = 'red',
            turn_number = 1,
            state = $2::jsonb,
            updated_at = now()
        WHERE id = $1
        """,
        game_id,
        json.dumps(state_dict),
    )

    await create_game_pokemon_map(db, game_id, id_map)
