"""Tests for engine/moves.py — Task #3: standard piece move generation."""

import pytest
from engine import GameState, Piece, PieceType, Team, Item
from engine.moves import get_legal_moves, Move, ActionType


# ---------------------------------------------------------------------------
# Board helpers
# ---------------------------------------------------------------------------

def empty_state(active: Team = Team.RED) -> GameState:
    board = [[None] * 8 for _ in range(8)]
    return GameState(
        board=board,
        active_player=active,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def place(state: GameState, piece_type: PieceType, team: Team, row: int, col: int) -> Piece:
    piece = Piece.create(piece_type, team, row, col)
    state.board[row][col] = piece
    return piece


def moves_of_type(moves: list, action: ActionType) -> list:
    return [m for m in moves if m.action_type == action]


def targets(moves: list) -> set:
    return {(m.target_row, m.target_col) for m in moves}


def moves_from(moves: list, row: int, col: int) -> list:
    """Filter moves to those originating from a specific square."""
    return [m for m in moves if m.piece_row == row and m.piece_col == col]


# ---------------------------------------------------------------------------
# TestSquirtleMoves
# ---------------------------------------------------------------------------

class TestSquurtleMoves:
    def test_open_center_move_count(self):
        # Squirtle at (3,3) on empty board: 3+4 horizontal + 3+4 vertical = 14 MOVE squares
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 14

    def test_no_attacks_on_empty_board(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        assert moves_of_type(get_legal_moves(state), ActionType.ATTACK) == []

    def test_attacks_enemy_in_file(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 6)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert len(atk) == 1
        assert atk[0].target_row == 3 and atk[0].target_col == 6

    def test_enemy_blocks_squares_behind_it(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 5)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 6) not in move_targets
        assert (3, 7) not in move_targets

    def test_friendly_blocks_ray_and_no_attack(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.BULBASAUR, Team.RED, 3, 5)
        all_moves = get_legal_moves(state)
        all_tgts = targets(all_moves)
        assert (3, 5) not in all_tgts  # friendly — not attackable
        assert (3, 6) not in all_tgts  # behind friendly — blocked

    def test_moves_only_horizontal_and_vertical(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 4)
        for m in moves_of_type(get_legal_moves(state), ActionType.MOVE):
            assert m.target_row == 4 or m.target_col == 4, \
                f"Rook move is diagonal: ({m.target_row},{m.target_col})"

    def test_no_moves_off_board(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        for m in get_legal_moves(state):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8

    def test_corner_move_count(self):
        # From (0,0): 7 right + 7 down = 14 MOVE squares
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 14


# ---------------------------------------------------------------------------
# TestCharmanderMoves
# ---------------------------------------------------------------------------

class TestCharmanderMoves:
    def test_open_center_move_count(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 8

    def test_corner_limits_moves(self):
        # From (0,0): only (1,2) and (2,1) are reachable
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 0, 0)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert move_targets == {(1, 2), (2, 1)}

    def test_jumps_over_friendly(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        # Fill all adjacent squares with friendlies — knight still reaches all 8 L-jumps
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (dr, dc) != (0, 0):
                    place(state, PieceType.SQUIRTLE, Team.RED, 3 + dr, 3 + dc)
        charmander_moves = moves_from(get_legal_moves(state), 3, 3)
        assert len(moves_of_type(charmander_moves, ActionType.MOVE)) == 8

    def test_jumps_over_enemy(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 4, 3)
        # Adjacent enemies don't block knight jumps
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 8

    def test_attacks_enemy_at_jump_square(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 1, 2)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert len(atk) == 1
        assert (atk[0].target_row, atk[0].target_col) == (1, 2)

    def test_does_not_attack_friendly_at_jump_square(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 2)
        all_tgts = targets(get_legal_moves(state))
        assert (1, 2) not in all_tgts

    def test_no_moves_off_board(self):
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 0, 1)
        for m in get_legal_moves(state):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8


# ---------------------------------------------------------------------------
# TestBulbasaurMoves
# ---------------------------------------------------------------------------

class TestBulbasaurMoves:
    def test_open_center_move_count(self):
        # Bishop at (3,3): NE=3, NW=3, SE=4, SW=3 = 13
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 13

    def test_moves_only_diagonal(self):
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 4, 4)
        for m in moves_of_type(get_legal_moves(state), ActionType.MOVE):
            dr = abs(m.target_row - 4)
            dc = abs(m.target_col - 4)
            assert dr == dc and dr > 0, \
                f"Non-diagonal bishop move: ({m.target_row},{m.target_col})"

    def test_enemy_blocks_diagonal_ray(self):
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (5, 5) not in move_targets  # enemy → attack square, not move
        assert (6, 6) not in move_targets  # behind enemy → blocked
        assert (7, 7) not in move_targets

    def test_attacks_enemy_on_diagonal(self):
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert len(atk) == 1
        assert (atk[0].target_row, atk[0].target_col) == (5, 5)

    def test_friendly_blocks_ray_no_attack(self):
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        all_tgts = targets(get_legal_moves(state))
        assert (5, 5) not in all_tgts
        assert (6, 6) not in all_tgts

    def test_no_moves_off_board(self):
        state = empty_state()
        place(state, PieceType.BULBASAUR, Team.RED, 0, 0)
        for m in get_legal_moves(state):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8


# ---------------------------------------------------------------------------
# TestMewMoves
# ---------------------------------------------------------------------------

class TestMewMoves:
    def test_open_center_move_count(self):
        # Queen at (3,3): 14 rook + 13 bishop = 27 MOVE squares
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 27

    def test_attack_generates_four_slots_per_target(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 6)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert len(atk) == 4
        assert {m.move_slot for m in atk} == {0, 1, 2, 3}
        assert all(m.target_row == 3 and m.target_col == 6 for m in atk)

    def test_attack_slots_for_multiple_enemies(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 6)
        place(state, PieceType.BULBASAUR, Team.BLUE, 5, 5)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert len(atk) == 8  # 4 slots × 2 enemies

    def test_foresight_generated_when_available(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 6)
        fs = moves_of_type(get_legal_moves(state), ActionType.FORESIGHT)
        assert len(fs) > 0
        assert (3, 6) in targets(fs)  # enemy square is a valid foresight target

    def test_foresight_targets_empty_squares(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        fs = moves_of_type(get_legal_moves(state), ActionType.FORESIGHT)
        # All 27 reachable squares on empty board are valid foresight targets
        assert len(fs) == 27

    def test_foresight_blocked_after_used_last_turn(self):
        state = empty_state()
        state.foresight_used_last_turn[Team.RED] = True
        place(state, PieceType.MEW, Team.RED, 3, 3)
        assert moves_of_type(get_legal_moves(state), ActionType.FORESIGHT) == []

    def test_foresight_available_for_blue_when_only_red_blocked(self):
        state = empty_state(active=Team.BLUE)
        state.foresight_used_last_turn[Team.RED] = True
        state.foresight_used_last_turn[Team.BLUE] = False
        place(state, PieceType.MEW, Team.BLUE, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.FORESIGHT)) > 0

    def test_foresight_move_slot_is_none(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        for m in moves_of_type(get_legal_moves(state), ActionType.FORESIGHT):
            assert m.move_slot is None

    def test_attacks_have_move_slot_in_range(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 6)
        for m in moves_of_type(get_legal_moves(state), ActionType.ATTACK):
            assert m.move_slot in (0, 1, 2, 3)

    def test_moves_have_no_move_slot(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        for m in moves_of_type(get_legal_moves(state), ActionType.MOVE):
            assert m.move_slot is None

    def test_friendly_blocks_queen_ray(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 5)
        mew_moves = moves_from(get_legal_moves(state), 3, 3)
        mew_tgts = targets(mew_moves)
        assert (3, 5) not in mew_tgts
        assert (3, 6) not in mew_tgts


# ---------------------------------------------------------------------------
# TestTradeMoves
# ---------------------------------------------------------------------------

class TestTradeMoves:
    def test_trade_with_adjacent_friendly_different_item(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)    # WATERSTONE
        place(state, PieceType.CHARMANDER, Team.RED, 3, 4)  # FIRESTONE
        trades = moves_of_type(get_legal_moves(state), ActionType.TRADE)
        assert any(m.target_row == 3 and m.target_col == 4 for m in trades)

    def test_no_trade_with_same_item(self):
        # Two Squirtles both hold WATERSTONE
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.TRADE) == []

    def test_no_trade_with_enemy(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.TRADE) == []

    def test_trade_with_diagonal_neighbor(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)    # WATERSTONE
        place(state, PieceType.CHARMANDER, Team.RED, 4, 4)  # FIRESTONE
        trades = moves_of_type(get_legal_moves(state), ActionType.TRADE)
        assert any(m.target_row == 4 and m.target_col == 4 for m in trades)

    def test_trade_with_none_item(self):
        # Squirtle (WATERSTONE) can trade with Eevee (NONE)
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.EEVEE, Team.RED, 3, 4)
        trades = moves_of_type(get_legal_moves(state), ActionType.TRADE)
        assert any(m.target_row == 3 and m.target_col == 4 for m in trades)

    def test_no_trade_off_board(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        for m in moves_of_type(get_legal_moves(state), ActionType.TRADE):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8


# ---------------------------------------------------------------------------
# TestGetLegalMoves
# ---------------------------------------------------------------------------

class TestGetLegalMoves:
    def test_empty_board_returns_empty(self):
        assert get_legal_moves(empty_state()) == []

    def test_returns_moves_for_active_player_only(self):
        state = empty_state(active=Team.RED)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        for m in get_legal_moves(state):
            assert m.piece_row == 3 and m.piece_col == 3

    def test_aggregates_all_active_pieces(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        place(state, PieceType.CHARMANDER, Team.RED, 7, 7)
        origins = {(m.piece_row, m.piece_col) for m in get_legal_moves(state)}
        assert (0, 0) in origins
        assert (7, 7) in origins

    def test_unimplemented_piece_types_skipped_gracefully(self):
        # Pokeball (Task #4) and Pikachu (Task #5) not yet wired up
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 1, 0)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        assert get_legal_moves(state) == []

    def test_move_origin_matches_piece_position(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 2, 5)
        for m in get_legal_moves(state):
            assert m.piece_row == 2 and m.piece_col == 5

    def test_no_move_targets_own_square(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 4, 4)
        for m in get_legal_moves(state):
            assert not (m.target_row == 4 and m.target_col == 4)
