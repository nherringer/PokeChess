"""
Monte Carlo Tree Search bot for PokeChess.

MCTS loop (per iteration):
  1. Selection   — traverse tree via UCB1 until unexplored child or terminal
  2. Expansion   — add one new child node to the tree
  3. Simulation  — random rollout to game end (or rollout_depth_limit moves)
  4. Backprop    — update wins/visits from expanded node back to root

Tree reuse: after a move is made and the opponent responds, the subtree
rooted at (our_move → opponent_response) is retained as the new root.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from bot.ucb import DEFAULT_C

if TYPE_CHECKING:
    from engine.state import GameState, Team
    from engine.moves import Move

DEFAULT_ROLLOUT_DEPTH_LIMIT = 150


class MCTSNode:
    """A node in the MCTS tree."""
    pass


class MCTS:
    """
    MCTS bot. Usage:
        bot = MCTS(time_budget=3.0)
        move = bot.select_move(state)
        bot.advance(move, opponent_move)  # reuse subtree

    Args:
        time_budget:         Seconds per move (controls difficulty).
        rollout_depth_limit: Max moves per simulation before hp_winner() tiebreak.
        exploration_c:       UCB1 exploration constant (default sqrt(2)).
    """

    def __init__(
        self,
        time_budget: float = 3.0,
        rollout_depth_limit: int = DEFAULT_ROLLOUT_DEPTH_LIMIT,
        exploration_c: float = DEFAULT_C,
    ) -> None:
        self.time_budget = time_budget
        self.rollout_depth_limit = rollout_depth_limit
        self.exploration_c = exploration_c
