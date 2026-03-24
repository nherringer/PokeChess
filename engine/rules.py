"""
Move execution, damage resolution, stochastic outcomes, and win condition.

apply_move(state, move) returns one or more (resulting_state, probability) tuples.
Most moves are deterministic and return a single tuple with probability 1.0.
Pokeball interactions return two tuples: (capture_state, 0.5), (fail_state, 0.5)
— or (state, 1.0) / (state, 0.0) for Masterball/Pikachu edge cases.

is_terminal(state) returns (is_done, winner) where winner is Team or None (draw).
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, Team
    from .moves import Move


def apply_move(state: GameState, move: Move) -> list[tuple[GameState, float]]:
    """
    Apply move to state. Returns list of (new_state, probability) pairs.
    Deterministic moves return a single pair with probability 1.0.
    Implemented in Task #6.
    """
    raise NotImplementedError


def is_terminal(state: GameState) -> tuple[bool, Optional[Team]]:
    """
    Check if the game is over.
    Returns (True, winning_team) or (True, None) for draw, or (False, None).
    Implemented in Task #7.
    """
    raise NotImplementedError


def hp_winner(state: GameState) -> Optional[Team]:
    """
    Tiebreaker for rollout depth limit: team with higher total HP fraction wins.
    Returns None if equal (true draw).
    """
    raise NotImplementedError
