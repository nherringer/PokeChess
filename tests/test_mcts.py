"""Tests for MCTS bot quality and correctness (Tasks #8-11)."""
import math
import pytest

from engine.state import GameState, Team, PieceType, Item, Piece, ForesightEffect
from engine.moves import get_legal_moves, ActionType
from engine.rules import apply_move, is_terminal
from engine.zobrist import build_zobrist_table, hash_state, ZOBRIST_TABLE
from bot.ucb import ucb1, DEFAULT_C
from bot.transposition import TranspositionTable
from bot.mcts import MCTS, MCTSNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def kings_only_state(active=Team.RED):
    board = [[None] * 8 for _ in range(8)]
    pikachu = Piece.create(PieceType.PIKACHU, Team.RED,  0, 4)
    eevee   = Piece.create(PieceType.EEVEE,   Team.BLUE, 7, 4)
    board[0][4] = pikachu
    board[7][4] = eevee
    return GameState(
        board=board,
        active_player=active,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


# ---------------------------------------------------------------------------
# UCB1 (Task #9)
# ---------------------------------------------------------------------------

def test_ucb1_unvisited_returns_inf():
    assert ucb1(0, 0, 10) == float('inf')

def test_ucb1_unvisited_regardless_of_wins():
    assert ucb1(5, 0, 100) == float('inf')

def test_ucb1_formula():
    expected = 5 / 10 + 1.0 * math.sqrt(math.log(100) / 10)
    assert abs(ucb1(5, 10, 100, c=1.0) - expected) < 1e-9

def test_ucb1_higher_win_rate_gives_higher_score():
    assert ucb1(9, 10, 100, c=DEFAULT_C) > ucb1(1, 10, 100, c=DEFAULT_C)

def test_ucb1_exploration_increases_with_parent_visits():
    assert ucb1(5, 10, 1000, c=DEFAULT_C) > ucb1(5, 10, 100, c=DEFAULT_C)


# ---------------------------------------------------------------------------
# Zobrist hashing (part of Task #8)
# ---------------------------------------------------------------------------

def test_zobrist_same_state_same_hash():
    assert hash_state(GameState.new_game(), ZOBRIST_TABLE) == \
           hash_state(GameState.new_game(), ZOBRIST_TABLE)

def test_zobrist_different_active_player_different_hash():
    s1 = GameState.new_game()
    s2 = s1.copy()
    s2.active_player = Team.BLUE
    assert hash_state(s1, ZOBRIST_TABLE) != hash_state(s2, ZOBRIST_TABLE)

def test_zobrist_different_board_different_hash():
    s1 = GameState.new_game()
    s2 = s1.copy()
    piece = s2.board[0][0]
    s2.board[0][0] = None
    s2.board[2][0] = piece
    piece.row, piece.col = 2, 0
    assert hash_state(s1, ZOBRIST_TABLE) != hash_state(s2, ZOBRIST_TABLE)

def test_zobrist_custom_seed_differs():
    alt = build_zobrist_table(seed=99)
    s   = GameState.new_game()
    assert hash_state(s, ZOBRIST_TABLE) != hash_state(s, alt)


# ---------------------------------------------------------------------------
# TranspositionTable (Task #10)
# ---------------------------------------------------------------------------

def test_tt_empty_returns_zero():
    assert TranspositionTable().get(12345) == (0.0, 0)

def test_tt_update_and_get():
    tt = TranspositionTable()
    tt.update(1, 1.0)
    tt.update(1, 1.0)
    tt.update(1, 0.0)
    assert tt.get(1) == (2.0, 3)

def test_tt_draw_delta():
    tt = TranspositionTable()
    tt.update(7, 0.5)
    assert tt.get(7) == (0.5, 1)

def test_tt_independent_hashes():
    tt = TranspositionTable()
    tt.update(1, 1.0)
    tt.update(2, 0.0)
    assert tt.get(1) == (1.0, 1)
    assert tt.get(2) == (0.0, 1)

def test_tt_len():
    tt = TranspositionTable()
    tt.update(1, 1.0)
    tt.update(2, 0.5)
    assert len(tt) == 2


# ---------------------------------------------------------------------------
# MCTSNode (Task #8)
# ---------------------------------------------------------------------------

def test_node_not_terminal_at_start():
    assert not MCTSNode(GameState.new_game())._terminal

def test_node_expand_child_is_legal():
    state = GameState.new_game()
    node  = MCTSNode(state)
    child = node.expand()
    assert child.move in get_legal_moves(state)

def test_node_expand_child_added_to_children():
    node  = MCTSNode(GameState.new_game())
    child = node.expand()
    assert child in node.children

def test_node_fully_expanded_after_all_moves():
    state   = GameState.new_game()
    node    = MCTSNode(state)
    n_legal = len(get_legal_moves(state))
    for _ in range(n_legal):
        node.expand()
    assert node.is_fully_expanded

def test_node_select_child_returns_highest_ucb():
    root = MCTSNode(GameState.new_game())
    root.visits = 100
    c1 = MCTSNode(GameState.new_game())
    c1.wins, c1.visits = 90, 100
    c2 = MCTSNode(GameState.new_game())
    c2.wins, c2.visits = 10, 100
    root.children = [c1, c2]
    assert root.select_child(DEFAULT_C) is c1


# ---------------------------------------------------------------------------
# MCTS integration (Tasks #8, #11)
# ---------------------------------------------------------------------------

def test_mcts_returns_legal_move():
    state = GameState.new_game()
    move  = MCTS(time_budget=0.1).select_move(state)
    assert move in get_legal_moves(state)

def test_mcts_runs_iterations():
    state = GameState.new_game()
    bot   = MCTS(time_budget=0.2)
    bot.select_move(state)
    assert bot._root is not None
    assert bot._root.visits > 0
    assert len(bot._root.children) > 0

def test_mcts_with_transposition_table():
    tt  = TranspositionTable()
    bot = MCTS(time_budget=0.1, transposition=tt)
    bot.select_move(GameState.new_game())
    assert len(tt) > 0

def test_mcts_advance_reuses_subtree():
    state = GameState.new_game()
    bot   = MCTS(time_budget=0.2)
    move  = bot.select_move(state)

    new_state = apply_move(state, move)[0][0]
    opp_moves = get_legal_moves(new_state)
    if not opp_moves:
        return

    opp_move = opp_moves[0]
    bot.advance(move, opp_move)

    state2 = apply_move(new_state, opp_move)[0][0]
    move2  = bot.select_move(state2)
    assert move2 in get_legal_moves(state2)

def test_mcts_legal_move_kings_only():
    state = kings_only_state()
    move  = MCTS(time_budget=0.1).select_move(state)
    assert move in get_legal_moves(state)

def test_mcts_picks_winning_attack():
    """Bot should choose the move that immediately wins when it's obvious."""
    board = [[None] * 8 for _ in range(8)]
    pikachu = Piece.create(PieceType.PIKACHU, Team.RED,  3, 3)
    eevee   = Piece.create(PieceType.EEVEE,   Team.BLUE, 3, 4)
    eevee.current_hp = 10   # one normal hit away from KO
    board[3][3] = pikachu
    board[3][4] = eevee
    state = GameState(
        board=board,
        active_player=Team.RED,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )
    bot  = MCTS(time_budget=0.5)
    move = bot.select_move(state)
    assert move.action_type == ActionType.ATTACK
    assert (move.target_row, move.target_col) == (3, 4)

def test_mcts_warm_start_affects_node():
    """Nodes warm-started from the transposition table carry prior wins/visits."""
    tt = TranspositionTable()
    state = GameState.new_game()
    h = hash_state(state, ZOBRIST_TABLE)
    tt.update(h, 1.0)   # record one win for this position

    bot  = MCTS(time_budget=0.05, transposition=tt)
    bot._root = MCTSNode(state)
    bot._warm_start(bot._root)
    assert bot._root.visits == 1
    assert bot._root.wins   == 1.0
