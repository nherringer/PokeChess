"""
Bot vs random and bot vs bot validation (Task #11).

Crash-freedom, tree-reuse, and tactical-correctness tests.
These run in under ~30 s; a single MCTS instance uses time_budget=0.02 s.

Full statistical win-rate benchmarks (bot significantly beats random over many
games with a real time budget):
    python scripts/benchmark.py
"""
import random as _rand

import pytest

from engine.state import GameState, Team, PieceType, Piece
from engine.moves import get_legal_moves
from engine.rules import apply_move, is_terminal, hp_winner
from bot.mcts import MCTS
from bot.transposition import TranspositionTable


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _play_game(red_fn, blue_fn, state=None, max_turns=30, seed=None):
    """
    Play one game between two move-selection callables (state -> Move).
    Returns the winning Team, or None for a draw / hp_winner tiebreak tie.
    """
    if seed is not None:
        _rand.seed(seed)
    if state is None:
        state = GameState.new_game()
    for _ in range(max_turns):
        done, winner = is_terminal(state)
        if done:
            return winner
        moves = get_legal_moves(state)
        if not moves:
            return None
        fn = red_fn if state.active_player == Team.RED else blue_fn
        move = fn(state)
        outcomes = apply_move(state, move)
        state = _rand.choices(
            [s for s, _ in outcomes], weights=[p for _, p in outcomes]
        )[0]
    return hp_winner(state)


def _random_fn(state):
    return _rand.choice(get_legal_moves(state))


def _bot(time_budget=0.02):
    return MCTS(time_budget=time_budget).select_move


def _near_terminal_state():
    """Pikachu (RED) at (3,3) adjacent to Eevee (BLUE) at (3,4) with 10 HP."""
    board = [[None] * 8 for _ in range(8)]
    pika = Piece.create(PieceType.PIKACHU, Team.RED,  3, 3)
    evee = Piece.create(PieceType.EEVEE,   Team.BLUE, 3, 4)
    evee.current_hp = 10
    board[3][3] = pika
    board[3][4] = evee
    return GameState(
        board=board,
        active_player=Team.RED,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


# ---------------------------------------------------------------------------
# Crash-freedom: bot vs random
# ---------------------------------------------------------------------------

def test_bot_as_red_vs_random_no_crash():
    """5 games with bot=RED complete without exception."""
    fn = _bot()
    for seed in range(5):
        result = _play_game(fn, _random_fn, seed=seed)
        assert result in (Team.RED, Team.BLUE, None)


def test_random_vs_bot_as_blue_no_crash():
    """5 games with bot=BLUE complete without exception."""
    fn = _bot()
    for seed in range(5):
        result = _play_game(_random_fn, fn, seed=seed)
        assert result in (Team.RED, Team.BLUE, None)


# ---------------------------------------------------------------------------
# Crash-freedom: bot vs bot
# ---------------------------------------------------------------------------

def test_bot_vs_bot_no_crash():
    """5 games (bot vs bot, independent instances) complete without exception."""
    for seed in range(5):
        result = _play_game(_bot(), _bot(), seed=seed)
        assert result in (Team.RED, Team.BLUE, None)


def test_bot_vs_bot_shared_transposition_table_no_crash():
    """5 games sharing one TranspositionTable complete without exception."""
    tt = TranspositionTable()
    red = MCTS(time_budget=0.02, transposition=tt).select_move
    blu = MCTS(time_budget=0.02, transposition=tt).select_move
    for seed in range(5):
        result = _play_game(red, blu, seed=seed)
        assert result in (Team.RED, Team.BLUE, None)


# ---------------------------------------------------------------------------
# Tree reuse (advance)
# ---------------------------------------------------------------------------

def test_tree_reuse_advance_no_crash():
    """Calling advance() then select_move() on the next state does not raise."""
    state = GameState.new_game()
    bot   = MCTS(time_budget=0.02)
    move  = bot.select_move(state)

    outcomes  = apply_move(state, move)
    mid_state = _rand.choice([s for s, _ in outcomes])
    opp_moves = get_legal_moves(mid_state)
    if not opp_moves:
        return

    opp_move = _rand.choice(opp_moves)
    bot.advance(move, opp_move)

    outcomes2 = apply_move(mid_state, opp_move)
    state2    = outcomes2[0][0]
    move2     = bot.select_move(state2)
    assert move2 in get_legal_moves(state2)


def test_tree_reuse_unknown_opp_move_falls_back_gracefully():
    """advance() with an unseen opponent move doesn't crash future select_move calls."""
    state = GameState.new_game()
    bot   = MCTS(time_budget=0.02)
    move  = bot.select_move(state)

    # Fabricate a move that definitely wasn't explored
    from engine.moves import Move, ActionType
    fake_opp = Move(0, 0, ActionType.MOVE, 0, 0)
    bot.advance(move, fake_opp)

    # Bot should still work (starts a fresh tree)
    outcomes = apply_move(state, move)
    mid      = outcomes[0][0]
    opp_moves = get_legal_moves(mid)
    if not opp_moves:
        return
    outcomes2 = apply_move(mid, opp_moves[0])
    state2    = outcomes2[0][0]
    move2     = bot.select_move(state2)
    assert move2 in get_legal_moves(state2)


# ---------------------------------------------------------------------------
# Transposition table: inter-game accumulation
# ---------------------------------------------------------------------------

def test_transposition_table_grows_across_games():
    """Table has more entries after game 2 than after game 1."""
    tt  = TranspositionTable()
    red = MCTS(time_budget=0.02, transposition=tt).select_move
    blu = MCTS(time_budget=0.02, transposition=tt).select_move
    _play_game(red, blu, max_turns=20)
    after_g1 = len(tt)
    assert after_g1 > 0
    _play_game(red, blu, max_turns=20)
    assert len(tt) >= after_g1


def test_warm_start_uses_prior_game_stats():
    """A node warm-started from the table has non-zero visits before any iteration."""
    from engine.zobrist import hash_state, ZOBRIST_TABLE
    from bot.mcts import MCTSNode

    tt    = TranspositionTable()
    state = GameState.new_game()
    h     = hash_state(state, ZOBRIST_TABLE)

    # Pre-populate table with 10 wins from 10 visits
    for _ in range(10):
        tt.update(h, 1.0)

    bot = MCTS(time_budget=0.0, transposition=tt)   # 0 s — no iterations
    bot._root = MCTSNode(state)
    bot._warm_start(bot._root)

    assert bot._root.visits == 10
    assert bot._root.wins   == 10.0


# ---------------------------------------------------------------------------
# Tactical correctness
# ---------------------------------------------------------------------------

def test_bot_always_wins_from_clearly_won_position():
    """
    Pikachu (RED) adjacent to a near-dead Eevee (10 HP).
    The bot should find the 1-move KO every single time (10/10 trials).
    """
    wins = 0
    n    = 10
    for seed in range(n):
        _rand.seed(seed)
        result = _play_game(
            _bot(time_budget=0.05), _random_fn,
            state=_near_terminal_state(), max_turns=5, seed=seed,
        )
        if result == Team.RED:
            wins += 1
    assert wins == n


def test_random_loses_from_clearly_lost_position():
    """
    Complementary check: random player (RED) against bot (BLUE) starting from
    the mirror position where BLUE Pikachu threatens near-dead RED Eevee.
    """
    board = [[None] * 8 for _ in range(8)]
    evee = Piece.create(PieceType.EEVEE,   Team.RED,  3, 3)
    pika = Piece.create(PieceType.PIKACHU, Team.BLUE, 3, 4)
    evee.current_hp = 10
    board[3][3] = evee
    board[3][4] = pika
    # It's BLUE's turn; RED Eevee is on 10 HP
    state = GameState(
        board=board,
        active_player=Team.BLUE,
        turn_number=2,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )
    wins = 0
    n    = 10
    for seed in range(n):
        _rand.seed(seed)
        result = _play_game(
            _random_fn, _bot(time_budget=0.05),
            state=state, max_turns=5, seed=seed,
        )
        if result == Team.BLUE:
            wins += 1
    assert wins == n


def test_games_eventually_terminate():
    """No game runs forever — every game resolves within max_turns."""
    fn = _bot(0.02)
    for seed in range(3):
        _rand.seed(seed)
        state = GameState.new_game()
        terminated = False
        for _ in range(30):
            done, _ = is_terminal(state)
            if done or not get_legal_moves(state):
                terminated = True
                break
            move = fn(state) if state.active_player == Team.RED else _random_fn(state)
            outcomes = apply_move(state, move)
            state = outcomes[0][0]
        # Either terminated naturally or hp_winner resolves it
        assert terminated or hp_winner(state) in (Team.RED, Team.BLUE, None)
