"""
UCB1 selection formula for MCTS.

UCB1(node) = wins/visits + C * sqrt(ln(parent_visits) / node_visits)

C is the exploration constant (default sqrt(2)).
  - Lower C: more exploitative, plays known-good moves
  - Higher C: more exploratory, investigates less-visited branches

Unvisited nodes return infinity to ensure they are always explored
before revisiting any already-visited node.

Implemented in Task #9.
"""

from __future__ import annotations
import math

DEFAULT_C = math.sqrt(2)


def ucb1(wins: float, visits: int, parent_visits: int, c: float = DEFAULT_C) -> float:
    """
    Compute UCB1 score. Returns inf for unvisited nodes.
    Implemented in Task #9.
    """
    raise NotImplementedError
