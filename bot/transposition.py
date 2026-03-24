"""
Persistent transposition table for inter-game learning.

Maps Zobrist hash → (wins, visits) and survives across games.
On tree node creation, existing stats warm-start the node rather
than starting from 0/0, giving the bot informed priors from
positions seen in previous games.

Implemented in Task #10.
"""

from __future__ import annotations
from typing import Optional


class TranspositionTable:
    """Global stats table. Persists across games for inter-game learning."""
    pass
