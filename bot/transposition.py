"""
Persistent transposition table for inter-game learning.

Maps Zobrist hash → (wins, visits) and survives across games.
On tree node creation, existing stats warm-start the node rather
than starting from 0/0, giving the bot informed priors from
positions seen in previous games.

wins always reflects the mover's perspective: wins for the player
who made the move to reach the hashed position.
"""

from __future__ import annotations


class TranspositionTable:
    """Global stats table. Persists across MCTS instances and games."""

    def __init__(self) -> None:
        self._data: dict[int, tuple[float, int]] = {}

    def get(self, h: int) -> tuple[float, int]:
        """Return (wins, visits) for hash h, or (0.0, 0) if unseen."""
        return self._data.get(h, (0.0, 0))

    def update(self, h: int, win_delta: float) -> None:
        """Add win_delta wins and 1 visit to the entry for hash h."""
        wins, visits = self._data.get(h, (0.0, 0))
        self._data[h] = (wins + win_delta, visits + 1)

    def __len__(self) -> int:
        return len(self._data)
