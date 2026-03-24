"""
Zobrist hashing for GameState — used by the transposition table.

A unique 64-bit integer is assigned at startup to each combination of
(row, col, PieceType, Team, hp_bucket, Item). The hash for a full board
is the XOR of all occupied-square hashes, plus hashes for turn and
pending foresight state.

hp_bucket = current_hp // 50  (groups HP into bands: 0, 50, 100, 150, 200, 250)
This keeps the table size manageable while preserving meaningful HP distinctions
given the discrete HP values used in PokeChess.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, PieceType, Team, Item


def build_zobrist_table(seed: int = 42) -> dict:
    """
    Pre-generate random 64-bit integers for all (row, col, piece_type, team,
    hp_bucket, item) combinations. Called once at module load.
    """
    raise NotImplementedError


def hash_state(state: GameState, table: dict) -> int:
    """Compute the Zobrist hash for a GameState."""
    raise NotImplementedError


# Module-level table, initialized on first import
ZOBRIST_TABLE: dict = {}
