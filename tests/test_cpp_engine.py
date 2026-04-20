"""
Correctness tests for the C++ rollout engine (pokechess_cpp).

These tests use run_rollout_with_rolls() — a deterministic interface that accepts
a pre-supplied list of floats instead of an internal RNG.  The same float list is
fed to the Python engine so both paths can be compared step-by-step.

Each float in the list is consumed in pairs (move_roll, pokeball_roll) per step:
  - move_roll  : selects which legal move to take  (idx = int(roll * n_moves) % n_moves)
  - pokeball_roll : pokeball capture outcome        (< 0.5 = capture, >= 0.5 = fail)

Tests are skipped (not failed) when the C++ extension is not yet built.
"""
from __future__ import annotations
import dataclasses
import pytest
import random

try:
    import pokechess_cpp as _cpp
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False

from engine.state import GameState, Team, PieceType
from engine.moves import get_legal_moves, ActionType
from engine.rules import apply_move, is_terminal, hp_winner

skip_if_no_cpp = pytest.mark.skipif(
    not CPP_AVAILABLE,
    reason="pokechess_cpp not built — run: python setup.py build_ext --inplace",
)


# ---------------------------------------------------------------------------
# Python reference rollout (mirrors C++ rollout_fixed logic exactly)
# ---------------------------------------------------------------------------

def py_rollout_fixed(state: GameState, rolls: list[float], depth: int) -> int:
    """
    Deterministic rollout using pre-supplied rolls.
    Returns 1 for RED win, 0 for BLUE win or draw.
    """
    ri = 0
    for _ in range(depth):
        done, winner = is_terminal(state)
        if done:
            return 1 if winner == Team.RED else 0
        moves = get_legal_moves(state)
        if not moves:
            return 0
        move_roll = rolls[ri] if ri < len(rolls) else 0.0;  ri += 1
        pb_roll   = rolls[ri] if ri < len(rolls) else 1.0;  ri += 1
        idx = int(move_roll * len(moves)) % len(moves)
        move = moves[idx]
        outcomes = apply_move(state, move)
        if len(outcomes) == 1:
            state = outcomes[0][0]
        else:
            # Stochastic (pokeball): use variable catch probability from apply_move
            state = outcomes[0][0] if pb_roll < outcomes[0][1] else outcomes[1][0]
    done, winner = is_terminal(state)
    if done:
        return 1 if winner == Team.RED else 0
    w = hp_winner(state)
    return 1 if w == Team.RED else 0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def encode(state: GameState) -> bytes:
    from cpp.state_codec import encode_state
    return encode_state(state)


def strip_items(state: GameState) -> GameState:
    """Return a copy with hidden_items cleared.

    C++ doesn't implement tall grass item mechanics yet.  Stripping hidden items
    ensures Python and C++ rollouts see the same game model (no items found,
    no overflow move variants generated) so the fixed-roll tests can compare
    outcomes exactly.  Remove this helper once C++ tall grass is fully ported.
    """
    return dataclasses.replace(state, hidden_items=[])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@skip_if_no_cpp
def test_encode_decode_roundtrip():
    """Encoding a fresh game state and running 0 rollouts should not crash."""
    state = GameState.new_game()
    buf = encode(state)
    assert isinstance(buf, bytes)
    assert len(buf) > 20
    red, blue, draws = _cpp.run_rollouts(buf, n_rollouts=0, depth_limit=10, seed=1)
    assert red == 0 and blue == 0 and draws == 0


@skip_if_no_cpp
def test_single_rollout_starting_position():
    """A single rollout from the starting position should complete without error."""
    state = GameState.new_game()
    buf = encode(state)
    red, blue, draws = _cpp.run_rollouts(buf, n_rollouts=1, depth_limit=150, seed=42)
    assert red + blue + draws == 1


@skip_if_no_cpp
def test_fixed_rolls_match_python_starting():
    """C++ and Python produce identical results for the same pre-supplied rolls."""
    rng = random.Random(7)
    rolls = [rng.random() for _ in range(600)]

    state = strip_items(GameState.new_game())
    buf = encode(state)

    py_result = py_rollout_fixed(state, rolls, depth=150)
    cpp_result = _cpp.run_rollout_with_rolls(buf, rolls, depth_limit=150)
    assert py_result == cpp_result, (
        f"Python returned {py_result}, C++ returned {cpp_result}"
    )


@skip_if_no_cpp
@pytest.mark.parametrize("seed", [1, 2, 3, 5, 13, 42, 99, 123])
def test_fixed_rolls_match_python_various_seeds(seed):
    """Fixed-rolls agreement holds across multiple random seeds."""
    rng = random.Random(seed)
    rolls = [rng.random() for _ in range(800)]

    state = strip_items(GameState.new_game())
    buf = encode(state)

    py_result = py_rollout_fixed(state, rolls, depth=150)
    cpp_result = _cpp.run_rollout_with_rolls(buf, rolls, depth_limit=150)
    assert py_result == cpp_result, (
        f"seed={seed}: Python={py_result}, C++={cpp_result}"
    )


@skip_if_no_cpp
def test_terminal_state_returns_immediately():
    """A state where the Red king is already gone should return BLUE immediately."""
    state = GameState.new_game()
    # Remove Pikachu (Red king)
    for row in state.board:
        for i, p in enumerate(row):
            if p is not None and p.piece_type == PieceType.PIKACHU:
                row[i] = None
    buf = encode(state)
    red, blue, draws = _cpp.run_rollouts(buf, n_rollouts=10, depth_limit=150, seed=1)
    assert blue == 10 and red == 0


@skip_if_no_cpp
def test_bulk_rollouts_sum():
    """run_rollouts result counts always sum to n_rollouts."""
    state = GameState.new_game()
    buf = encode(state)
    n = 200
    red, blue, draws = _cpp.run_rollouts(buf, n_rollouts=n, depth_limit=50, seed=7)
    assert red + blue + draws == n


@skip_if_no_cpp
def test_determinism_same_seed():
    """Same seed produces identical results across two calls."""
    state = GameState.new_game()
    buf = encode(state)
    r1 = _cpp.run_rollouts(buf, n_rollouts=50, depth_limit=100, seed=99)
    r2 = _cpp.run_rollouts(buf, n_rollouts=50, depth_limit=100, seed=99)
    assert r1 == r2


@skip_if_no_cpp
def test_different_seeds_differ():
    """Different seeds produce different results (probabilistically)."""
    state = GameState.new_game()
    buf = encode(state)
    r1 = _cpp.run_rollouts(buf, n_rollouts=100, depth_limit=100, seed=1)
    r2 = _cpp.run_rollouts(buf, n_rollouts=100, depth_limit=100, seed=2)
    # They might coincidentally match, but extremely unlikely with 100 rollouts
    assert r1 != r2
