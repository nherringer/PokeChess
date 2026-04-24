"""
Zobrist hashing for GameState — used by the transposition table.

A unique 64-bit integer is assigned at startup to each combination of
(row, col, PieceType, Team, hp_bucket, Item). The hash for a full board
is the XOR of all occupied-square hashes, plus hashes for turn, pending
foresight state, explored tall grass squares, and visible floor items.

hp_bucket = current_hp // 50  (groups HP into bands: 0, 50, 100, 150, 200, 250)
This keeps the table size manageable while preserving meaningful HP distinctions
given the discrete HP values used in PokeChess.

hidden_items are NOT hashed — neither player knows their identity, and the bot
operates on a masked state where they are invisible.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState

from .state import PieceType, Team, Item


def build_zobrist_table(seed: int = 42) -> dict:
    """
    Pre-generate random 64-bit integers for all (row, col, piece_type, team,
    hp_bucket, item) combinations. Called once at module load.
    """
    rng = random.Random(seed)

    def r64() -> int:
        return rng.getrandbits(64)

    table: dict = {}

    # Per-square piece occupancy: (row, col, piece_type, team, hp_bucket, item)
    for row in range(8):
        for col in range(8):
            for pt in PieceType:
                for team in Team:
                    # hp_bucket 0–5 covers 0–250 HP in steps of 50
                    for hp_bucket in range(6):
                        for item in Item:
                            table[('p', row, col, pt, team, hp_bucket, item)] = r64()

    # Active player
    for team in Team:
        table[('t', team)] = r64()

    # Pending foresight: (team, target_row, target_col, turns_until_resolution)
    # turns_away = resolves_on_turn - current_turn_number, clamped to 1–4
    for team in Team:
        for row in range(8):
            for col in range(8):
                for turns_away in range(1, 5):
                    table[('f', team, row, col, turns_away)] = r64()

    # Explored tall grass square: ('g', row, col) — XOR in when square is explored
    for row in range(8):
        for col in range(8):
            table[('g', row, col)] = r64()

    # Floor item visible on a square: ('i', row, col, item)
    for row in range(8):
        for col in range(8):
            for item in Item:
                table[('i', row, col, item)] = r64()

    return table


def hash_state(state: GameState, table: dict) -> int:
    """Compute the Zobrist hash for a GameState."""
    h = 0

    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is None:
                continue
            hp_bucket = p.current_hp // 50
            h ^= table.get(('p', r, c, p.piece_type, p.team, hp_bucket, p.held_item), 0)

    h ^= table.get(('t', state.active_player), 0)

    for team, fx in state.pending_foresight.items():
        if fx is None:
            continue
        turns_away = fx.resolves_on_turn - state.turn_number
        if 1 <= turns_away <= 4:
            h ^= table.get(('f', team, fx.target_row, fx.target_col, turns_away), 0)

    for (gr, gc) in state.tall_grass_explored:
        h ^= table.get(('g', gr, gc), 0)

    for fi in state.floor_items:
        h ^= table.get(('i', fi.row, fi.col, fi.item), 0)

    return h


# Module-level table, initialized on first import
ZOBRIST_TABLE: dict = build_zobrist_table()
