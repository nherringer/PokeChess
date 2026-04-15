"""
Monte Carlo Tree Search bot for PokeChess.

MCTS loop (per iteration):
  1. Selection   — traverse tree via UCB1 until unexplored child or terminal
  2. Expansion   — add one new child node to the tree
  3. Simulation  — random rollout to game end (or rollout_depth_limit moves)
  4. Backprop    — update wins/visits from expanded node back to root

wins accounting: each node stores wins for the player who made the move TO
reach it (= opponent of node.state.active_player). UCB1 selection at a node
therefore directly maximises the active player's win rate over children.

Tree reuse: after a move is made and the opponent responds, the subtree
rooted at (our_move → opponent_response) is retained as the new root.

Memory: MCTSNode stores no parent link. The backprop path is collected
during selection as a plain list. Without parent back-edges the tree is a
pure downward DAG — no reference cycles, so it is freed by reference
counting the moment the root is released (no GC needed).
"""

from __future__ import annotations

import random as _random
import time
from typing import Optional, TYPE_CHECKING

from bot.ucb import ucb1, DEFAULT_C
from bot.transposition import TranspositionTable
from engine.moves import get_legal_moves, Move, ActionType
from engine.rules import apply_move, is_terminal, hp_winner
from engine.state import GameState, Team, PieceType
from engine.zobrist import hash_state, ZOBRIST_TABLE

DEFAULT_ROLLOUT_DEPTH_LIMIT = 150

# ---------------------------------------------------------------------------
# Move bias helpers
# ---------------------------------------------------------------------------

_PIKACHU_TYPES: frozenset = frozenset({PieceType.PIKACHU, PieceType.RAICHU})


def _chase_pikachu_fn(bonus: float):
    """Return a bias function that rewards ATTACK moves targeting Pikachu/Raichu."""
    def _fn(move: Move, state: GameState) -> float:
        if move.action_type != ActionType.ATTACK:
            return 0.0
        target = state.board[move.target_row][move.target_col]
        if target is not None and target.piece_type in _PIKACHU_TYPES:
            return bonus
        return 0.0
    return _fn


def _prefer_pikachu_raichu_fn(bonus: float):
    """Return a bias function that rewards moves where the mover is Pikachu/Raichu."""
    def _fn(move: Move, state: GameState) -> float:
        piece = state.board[move.piece_row][move.piece_col]
        if piece is not None and piece.piece_type in _PIKACHU_TYPES:
            return bonus
        return 0.0
    return _fn


def _make_bias_fn(move_bias: Optional[str], bonus: float):
    """Resolve a move_bias string to a callable, or None for no bias."""
    if move_bias == "chase_pikachu":
        return _chase_pikachu_fn(bonus)
    if move_bias == "prefer_pikachu_raichu":
        return _prefer_pikachu_raichu_fn(bonus)
    return None

# ---------------------------------------------------------------------------
# C++ rollout engine (optional — falls back to pure Python if not built)
# ---------------------------------------------------------------------------

try:
    import pokechess_cpp as _cpp
    from cpp.state_codec import encode_state as _encode_state
    _CPP_AVAILABLE = True
except ImportError:
    _CPP_AVAILABLE = False

# Number of C++ rollouts to batch per MCTS expansion.
# Higher = fewer Python↔C++ round-trips; lower = finer-grained time checks.
_CPP_BATCH = 8


# ---------------------------------------------------------------------------
# Tree node
# ---------------------------------------------------------------------------

class MCTSNode:
    """A node in the MCTS tree."""

    __slots__ = (
        'state', 'move',
        'wins', 'visits', 'children',
        '_untried', '_terminal', '_winner', '_hash',
        'bias_bonus',
    )

    def __init__(
        self,
        state: GameState,
        move: Optional[Move] = None,
        bias_bonus: float = 0.0,
    ) -> None:
        self.state      = state
        self.move       = move
        self.wins       = 0.0
        self.visits     = 0
        self.bias_bonus = bias_bonus
        self.children: list[MCTSNode] = []

        # Lazy: populated on first call to _get_untried() / is_fully_expanded
        self._untried: Optional[list[Move]] = None

        # Cache terminal status (is_terminal is called frequently)
        done, winner = is_terminal(state)
        self._terminal: bool  = done
        self._winner: Optional[Team] = winner

        # Lazy Zobrist hash
        self._hash: Optional[int] = None

    @property
    def hash(self) -> int:
        if self._hash is None:
            self._hash = hash_state(self.state, ZOBRIST_TABLE)
        return self._hash

    def _get_untried(self) -> list[Move]:
        if self._untried is None:
            moves = [] if self._terminal else get_legal_moves(self.state)
            _random.shuffle(moves)
            self._untried = moves
        return self._untried

    @property
    def is_fully_expanded(self) -> bool:
        return self._terminal or len(self._get_untried()) == 0

    def select_child(self, c: float) -> MCTSNode:
        """Return the child with the highest UCB1 score, plus any persona bias bonus."""
        return max(
            self.children,
            key=lambda ch: ucb1(ch.wins, ch.visits, self.visits, c) + ch.bias_bonus,
        )

    def expand(self, bias_fn=None) -> MCTSNode:
        """Pop one untried move, sample its outcome, return the new child node."""
        untried = self._get_untried()
        move = untried.pop()            # shuffled on init, so this is random

        outcomes = apply_move(self.state, move)
        if len(outcomes) == 1:
            new_state = outcomes[0][0]
        else:
            # Stochastic (Pokéball capture): sample one outcome by probability
            new_state = _random.choices(
                [s for s, _ in outcomes],
                weights=[p for _, p in outcomes],
            )[0]

        bonus = bias_fn(move, self.state) if bias_fn is not None else 0.0
        child = MCTSNode(new_state, move=move, bias_bonus=bonus)
        self.children.append(child)
        return child


# ---------------------------------------------------------------------------
# MCTS bot
# ---------------------------------------------------------------------------

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
        transposition:       Optional shared TranspositionTable for inter-game learning.
    """

    def __init__(
        self,
        time_budget: float = 3.0,
        rollout_depth_limit: int = DEFAULT_ROLLOUT_DEPTH_LIMIT,
        exploration_c: float = DEFAULT_C,
        transposition: Optional[TranspositionTable] = None,
        move_bias: Optional[str] = None,
        bias_bonus: float = 0.15,
    ) -> None:
        self.time_budget         = time_budget
        self.rollout_depth_limit = rollout_depth_limit
        self.exploration_c       = exploration_c
        self.transposition       = transposition
        self._bias_fn            = _make_bias_fn(move_bias, bias_bonus)
        self._root: Optional[MCTSNode] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def ponder(self, state: GameState, should_stop) -> None:
        """
        Run MCTS indefinitely on state until should_stop() returns True.
        Reuses the existing tree if it matches state (same as select_move).
        Called from a background thread during the opponent's turn.
        """
        self._root = self._find_or_create_root(state)
        self._warm_start(self._root)
        while not should_stop():
            self._iterate()

    def select_move(self, state: GameState) -> Move:
        """
        Run MCTS for time_budget seconds and return the best move.
        Reuses the existing tree if it already represents this state.
        Falls back to a random legal move if no iterations complete.
        """
        self._root = self._find_or_create_root(state)
        self._warm_start(self._root)

        deadline = time.monotonic() + self.time_budget
        while time.monotonic() < deadline:
            self._iterate()

        if not self._root.children:
            return _random.choice(get_legal_moves(state))

        # Most-visited child is the most robust choice (less sensitive to outliers)
        return max(self._root.children, key=lambda ch: ch.visits).move

    def advance(self, our_move: Move, opp_move: Move) -> None:
        """
        Discard tree branches that are now unreachable and set the new root
        to the subtree reached via our_move → opp_move.

        If either move is not found in the current tree the root is cleared,
        causing select_move() to start a fresh tree on the next call.
        """
        if self._root is None:
            return

        # Find child for our move
        our_child = next((c for c in self._root.children if c.move == our_move), None)
        if our_child is None:
            self._root = None
            return

        # Find grandchild for the opponent's response
        opp_child = next(
            (c for c in our_child.children if c.move == opp_move), None
        )
        self._root = opp_child if opp_child is not None else our_child

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _find_or_create_root(self, state: GameState) -> MCTSNode:
        """Return the existing root if it matches state, otherwise create one."""
        if self._root is not None:
            h = hash_state(state, ZOBRIST_TABLE)
            if self._root.hash == h:
                return self._root
        return MCTSNode(state)

    def _warm_start(self, node: MCTSNode) -> None:
        """Initialise node wins/visits from the transposition table if not already visited."""
        if self.transposition is None or node.visits > 0:
            return
        w, v = self.transposition.get(node.hash)
        if v > 0:
            node.wins   = w
            node.visits = v

    def _iterate(self) -> None:
        """One full MCTS iteration: selection → expansion → simulation → backprop."""
        # 1. Selection: descend via UCB1, recording the path for backprop.
        #    No parent links are stored in nodes; the path list is the only
        #    record of the ancestry for this iteration.
        node = self._root
        path = [node]
        while node.is_fully_expanded and node.children:
            node = node.select_child(self.exploration_c)
            path.append(node)

        # 2. Expansion: grow the tree by one node
        if not node._terminal and not node.is_fully_expanded:
            node = node.expand(self._bias_fn)
            path.append(node)
            self._warm_start(node)

        # 3. Simulation: random rollout from the new node
        if _CPP_AVAILABLE and not node._terminal:
            self._iterate_cpp_batch(node, path)
            return
        winner = self._rollout(node)

        # 4. Backpropagation: update wins/visits up to the root
        self._backprop(path, winner)

    def _iterate_cpp_batch(self, node: MCTSNode, path: list) -> None:
        """Run _CPP_BATCH C++ rollouts for a single node and backprop all results."""
        buf = _encode_state(node.state)
        seed = _random.getrandbits(64)
        red, blue, draws = _cpp.run_rollouts(
            buf, _CPP_BATCH, self.rollout_depth_limit, seed
        )
        for _ in range(red):
            self._backprop(path, Team.RED)
        for _ in range(blue):
            self._backprop(path, Team.BLUE)
        for _ in range(draws):
            self._backprop(path, None)

    def _rollout(self, node: MCTSNode) -> Optional[Team]:
        """
        Random playout from node until terminal or rollout_depth_limit.
        Returns the winning Team, or None for a draw / depth-limit tie.
        """
        state = node.state
        for _ in range(self.rollout_depth_limit):
            if node._terminal:          # reuse cached check for the starting node only
                return node._winner
            done, winner = is_terminal(state)
            if done:
                return winner
            moves = get_legal_moves(state)
            if not moves:
                return None
            move = _random.choice(moves)
            outcomes = apply_move(state, move)
            if len(outcomes) == 1:
                state = outcomes[0][0]
            else:
                state = _random.choices(
                    [s for s, _ in outcomes],
                    weights=[p for _, p in outcomes],
                )[0]
        # Depth limit reached — use HP tiebreaker
        return hp_winner(state)

    def _backprop(self, path: list, winner: Optional[Team]) -> None:
        """
        Walk the recorded selection path from leaf to root, incrementing
        visits and crediting wins.

        wins at a node = wins for the player who MOVED TO that node
                       = opponent of node.state.active_player.
        This means UCB1 at a node naturally maximises the active player's
        win rate across its children.
        """
        for cur in reversed(path):
            cur.visits += 1

            # Player who made the move to reach cur
            mover = (Team.BLUE if cur.state.active_player == Team.RED else Team.RED)

            if winner is None:
                win_delta = 0.5
            elif winner == mover:
                win_delta = 1.0
            else:
                win_delta = 0.0

            cur.wins += win_delta

            if self.transposition is not None:
                self.transposition.update(cur.hash, win_delta)
