"""
Roster creation and piece-UUID injection for new games.

Each user's persistent roster (pokemon_pieces table):
  1 king, 1 queen, 2 rooks, 2 knights, 2 bishops = 8 pieces.

The roster is created at first game. UUIDs are injected into the starting
board's named pieces; pawns (pokeball/safetyball) get id=None.
"""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg

from engine.state import GameState, Team

from .serialization import IdMap, state_to_dict


# Back-rank layout: col → (role, species)
# Matches _place_starting_pieces() in engine/state.py
_BACK_RANK_RED = {
    0: ("rook", "squirtle"),
    1: ("knight", "charmander"),
    2: ("bishop", "bulbasaur"),
    3: ("queen", "mew"),
    # 4: king — handled separately (pikachu for red)
    5: ("bishop", "bulbasaur"),
    6: ("knight", "charmander"),
    7: ("rook", "squirtle"),
}
_BACK_RANK_BLUE = {
    0: ("rook", "squirtle"),
    1: ("knight", "charmander"),
    2: ("bishop", "bulbasaur"),
    3: ("queen", "mew"),
    # 4: king — handled separately (eevee for blue)
    5: ("bishop", "bulbasaur"),
    6: ("knight", "charmander"),
    7: ("rook", "squirtle"),
}

# Full roster definition: (role, species) tuples in creation order
_ROSTER = [
    ("king", None),    # species depends on side
    ("queen", "mew"),
    ("rook", "squirtle"),
    ("rook", "squirtle"),
    ("knight", "charmander"),
    ("knight", "charmander"),
    ("bishop", "bulbasaur"),
    ("bishop", "bulbasaur"),
]


async def ensure_roster(db: asyncpg.Connection, user_id: UUID, side: str) -> list[dict]:
    """Create the user's pokemon_pieces if they don't exist yet. Return the roster."""
    existing = await db.fetch(
        "SELECT id, role, species FROM pokemon_pieces WHERE owner_id = $1 ORDER BY created_at FOR UPDATE",
        user_id,
    )
    if existing:
        return [dict(r) for r in existing]

    king_species = "pikachu" if side == "red" else "eevee"
    pieces = []
    for role, species in _ROSTER:
        sp = king_species if role == "king" else species
        row = await db.fetchrow(
            """
            INSERT INTO pokemon_pieces (owner_id, role, species)
            VALUES ($1, $2, $3)
            RETURNING id, role, species
            """,
            user_id, role, sp,
        )
        pieces.append(dict(row))
    return pieces


def build_id_map(roster: list[dict], side: str) -> IdMap:
    """
    Map each roster piece to its starting board position.

    The roster has 8 pieces. We assign them to back-rank positions by role,
    left-to-right for duplicates (sorted by creation order = insert order).
    """
    back_row = 0 if side == "red" else 7
    layout = _BACK_RANK_RED if side == "red" else _BACK_RANK_BLUE

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
    for col, (role, _species) in layout.items():
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
