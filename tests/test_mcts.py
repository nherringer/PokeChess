"""Tests for MCTS bot quality and correctness (Tasks #8-11)."""
import math
import pytest

from engine.state import GameState, Team, PieceType, Item, Piece, ForesightEffect
from engine.moves import get_legal_moves, ActionType
from engine.rules import apply_move, is_terminal
from engine.zobrist import build_zobrist_table, hash_state, ZOBRIST_TABLE
from bot.ucb import ucb1, DEFAULT_C
from bot.transposition import TranspositionTable
from bot.mcts import MCTS, MCTSNode, _make_bias_fn


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


# ---------------------------------------------------------------------------
# Move bias — UCB1 bonus (persona behavior)
# ---------------------------------------------------------------------------

def _bias_state_blue_squirtle_vs_pikachu_and_charmander():
    """
    BLUE is active. Blue's Squirtle at (3,0) can slide right to attack Red's
    Pikachu at (3,3), or slide down to attack Red's Charmander at (6,0).
    Blue's Eevee at (7,4) is the Blue king.
    """
    board = [[None] * 8 for _ in range(8)]
    board[3][0] = Piece.create(PieceType.SQUIRTLE,   Team.BLUE, 3, 0)
    board[3][3] = Piece.create(PieceType.PIKACHU,    Team.RED,  3, 3)
    board[6][0] = Piece.create(PieceType.CHARMANDER, Team.RED,  6, 0)
    board[7][4] = Piece.create(PieceType.EEVEE,      Team.BLUE, 7, 4)
    return GameState(
        board=board,
        active_player=Team.BLUE,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def _bias_state_red_pikachu_and_squirtle():
    """
    RED is active. Red has Pikachu at (0,4) and Squirtle at (0,0).
    Blue's Eevee at (7,4) is the Blue king.
    """
    board = [[None] * 8 for _ in range(8)]
    board[0][4] = Piece.create(PieceType.PIKACHU,  Team.RED,  0, 4)
    board[0][0] = Piece.create(PieceType.SQUIRTLE, Team.RED,  0, 0)
    board[7][4] = Piece.create(PieceType.EEVEE,    Team.BLUE, 7, 4)
    return GameState(
        board=board,
        active_player=Team.RED,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def test_chase_pikachu_bonus_set_on_pikachu_attack_child():
    """
    With chase_pikachu bias, the child node for attacking Pikachu should
    carry bias_bonus=0.15; all other children should have bias_bonus=0.0.
    """
    state = _bias_state_blue_squirtle_vs_pikachu_and_charmander()
    bot = MCTS(time_budget=0.3, move_bias="chase_pikachu", bias_bonus=0.15)
    bot.select_move(state)

    pikachu_children = [
        c for c in bot._root.children
        if c.move.action_type == ActionType.ATTACK
        and c.move.target_row == 3 and c.move.target_col == 3
    ]
    other_children = [
        c for c in bot._root.children
        if not (c.move.action_type == ActionType.ATTACK
                and c.move.target_row == 3 and c.move.target_col == 3)
    ]

    assert pikachu_children, "Expected at least one child attacking Pikachu at (3,3)"
    assert all(c.bias_bonus == 0.15 for c in pikachu_children)
    assert all(c.bias_bonus == 0.0  for c in other_children)


def test_prefer_pikachu_raichu_bonus_set_on_pikachu_moves():
    """
    With prefer_pikachu_raichu bias, children whose move originates from
    Pikachu/Raichu carry bias_bonus=0.15; Squirtle moves carry 0.0.
    """
    state = _bias_state_red_pikachu_and_squirtle()
    bot = MCTS(time_budget=0.3, move_bias="prefer_pikachu_raichu", bias_bonus=0.15)
    bot.select_move(state)

    pikachu_children = [
        c for c in bot._root.children
        if c.move.piece_row == 0 and c.move.piece_col == 4
    ]
    squirtle_children = [
        c for c in bot._root.children
        if c.move.piece_row == 0 and c.move.piece_col == 0
    ]

    assert pikachu_children, "Expected at least one child from Pikachu at (0,4)"
    assert squirtle_children, "Expected at least one child from Squirtle at (0,0)"
    assert all(c.bias_bonus == 0.15 for c in pikachu_children)
    assert all(c.bias_bonus == 0.0  for c in squirtle_children)


def test_chase_pikachu_bonus_is_zero_when_no_pikachu_attackable_from_legal_moves():
    """chase_pikachu only adds bonus on ATTACKs targeting Pikachu/Raichu.

    Blue has no such attack among legal moves; a Red Pikachu may still be on
    the board. Every child should get bias_bonus 0.0.
    """
    board = [[None] * 8 for _ in range(8)]
    board[0][4] = Piece.create(PieceType.PIKACHU, Team.RED,  0, 4)
    board[7][4] = Piece.create(PieceType.EEVEE,   Team.BLUE, 7, 4)
    # Kings only — no Pikachu adjacent to Eevee, no immediate attack on Pikachu
    state = GameState(
        board=board,
        active_player=Team.BLUE,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )
    bot = MCTS(time_budget=0.2, move_bias="chase_pikachu", bias_bonus=0.15)
    bot.select_move(state)

    assert all(c.bias_bonus == 0.0 for c in bot._root.children)


def test_make_bias_fn_returns_none_for_unknown_bias():
    assert _make_bias_fn("unknown_bias", 0.15) is None


def test_make_bias_fn_returns_none_for_no_bias():
    assert _make_bias_fn(None, 0.15) is None


def test_node_bias_bonus_defaults_to_zero():
    node = MCTSNode(GameState.new_game())
    assert node.bias_bonus == 0.0


def test_select_child_uses_bias_bonus():
    """A child with a lower win rate but a bias bonus should beat a higher win-rate child."""
    root = MCTSNode(GameState.new_game())
    root.visits = 100

    c1 = MCTSNode(GameState.new_game())
    c1.wins, c1.visits, c1.bias_bonus = 50, 100, 0.0   # win rate 0.5, no bonus

    c2 = MCTSNode(GameState.new_game())
    c2.wins, c2.visits, c2.bias_bonus = 40, 100, 0.2   # win rate 0.4, +0.2 bonus

    root.children = [c1, c2]
    # c2 score = 0.4 + bonus 0.2 = 0.6 > c1 score = 0.5 (exploration terms equal)
    assert root.select_child(0.0) is c2  # c=0 isolates exploitation + bonus


def test_mcts_no_transposition_runs_normally():
    """MCTS without a transposition table runs correctly (use_transposition=False path)."""
    state = GameState.new_game()
    bot   = MCTS(time_budget=0.1, transposition=None)
    move  = bot.select_move(state)
    assert move in get_legal_moves(state)
