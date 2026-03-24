"""
Legal move generation for all PokeChess piece types.

A Move encodes one complete action a player can take on their turn:
  - Move a piece to an empty square
  - Attack a piece in range (attacker stays unless KO)
  - Use Foresight (Mew/Espeon only)
  - Trade held items with an adjacent teammate
  - Evolve (Pikachu→Raichu or Eevee→evo, costs the turn)
  - For Eevee only: move + attack in same turn (Quick Attack)

get_legal_moves(state) returns all legal moves for the active player.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, Piece, Team


class ActionType(Enum):
    MOVE       = auto()  # Move to empty square
    ATTACK     = auto()  # Attack target in movement range
    FORESIGHT  = auto()  # Delayed attack (Mew/Espeon)
    TRADE      = auto()  # Swap held items with adjacent teammate
    EVOLVE     = auto()  # Trigger evolution (costs full turn)
    QUICK_ATTACK = auto()  # Eevee only: move + attack same turn


@dataclass
class Move:
    piece_row: int
    piece_col: int
    action_type: ActionType
    # Destination square (for MOVE, EVOLVE) or target square (for ATTACK, FORESIGHT, TRADE)
    target_row: int
    target_col: int
    # Quick Attack only: secondary action destination after the primary
    secondary_row: Optional[int] = None
    secondary_col: Optional[int] = None
    # Which move slot Mew is using (0-3), None for all others
    move_slot: Optional[int] = None


def get_legal_moves(state: GameState) -> list[Move]:
    """Return all legal moves for the active player."""
    raise NotImplementedError
