"""Tests for engine/moves.py — Tasks #3 and #4: standard piece and pawn move generation."""

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

    def test_all_piece_types_handled(self):
        # Every piece type should generate moves without raising NotImplementedError
        state = empty_state()
        for col, pt in enumerate([
            PieceType.SQUIRTLE, PieceType.CHARMANDER, PieceType.BULBASAUR, PieceType.MEW,
            PieceType.PIKACHU, PieceType.RAICHU, PieceType.POKEBALL, PieceType.MASTERBALL,
        ]):
            place(state, pt, Team.RED, 0, col)
        for col, pt in enumerate([
            PieceType.EEVEE, PieceType.VAPOREON, PieceType.FLAREON,
            PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
        ]):
            place(state, pt, Team.RED, 1, col)
        moves = get_legal_moves(state)
        assert len(moves) > 0  # all types generate at least some moves

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


# ---------------------------------------------------------------------------
# TestPokeballMoves
# ---------------------------------------------------------------------------

class TestPokeballMoves:
    # RED forward = +row; BLUE forward = -row

    def test_open_center_move_count_red(self):
        # RED Pokeball at (3,3): forward 2, right 2, left 2, fwd-diag 2 = 8
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 8

    def test_open_center_move_count_blue(self):
        # BLUE Pokeball at (4,4): same geometry, forward = -row
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.POKEBALL, Team.BLUE, 4, 4)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 8

    def test_forward_direction_red(self):
        # RED moves toward higher rows
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        fwd_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (4, 3) in fwd_targets  # forward 1
        assert (5, 3) in fwd_targets  # forward 2
        assert (2, 3) not in fwd_targets  # backward — not allowed

    def test_forward_direction_blue(self):
        # BLUE moves toward lower rows
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.POKEBALL, Team.BLUE, 4, 4)
        fwd_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 4) in fwd_targets  # forward 1 for BLUE
        assert (2, 4) in fwd_targets  # forward 2 for BLUE
        assert (5, 4) not in fwd_targets  # backward — not allowed

    def test_horizontal_both_directions(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 4) in move_targets  # right 1
        assert (3, 5) in move_targets  # right 2
        assert (3, 2) in move_targets  # left 1
        assert (3, 1) in move_targets  # left 2

    def test_forward_diagonal_squares(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (4, 4) in move_targets  # forward-right diagonal
        assert (4, 2) in move_targets  # forward-left diagonal

    def test_no_backward_diagonal_for_pokeball(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        all_tgts = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (2, 4) not in all_tgts  # backward-right diagonal
        assert (2, 2) not in all_tgts  # backward-left diagonal

    def test_forward_blocked_at_1_prevents_reaching_2(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 3)  # friendly blocks forward
        pb_moves = moves_from(get_legal_moves(state), 3, 3)
        move_targets = targets(moves_of_type(pb_moves, ActionType.MOVE))
        assert (4, 3) not in move_targets  # friendly square — not movable
        assert (5, 3) not in move_targets  # can't pass through

    def test_enemy_forward_is_attack_not_move(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 4, 3)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        atk_targets = targets(moves_of_type(get_legal_moves(state), ActionType.ATTACK))
        assert (4, 3) not in move_targets
        assert (4, 3) in atk_targets
        assert (5, 3) not in move_targets  # blocked behind enemy

    def test_horizontal_blocked_at_1_prevents_reaching_2(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 4)  # friendly right-1
        pb_moves = moves_from(get_legal_moves(state), 3, 3)
        move_targets = targets(moves_of_type(pb_moves, ActionType.MOVE))
        assert (3, 4) not in move_targets
        assert (3, 5) not in move_targets  # blocked

    def test_attacks_enemy_on_horizontal(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert any(m.target_row == 3 and m.target_col == 4 for m in atk)

    def test_edge_column_limits_horizontal(self):
        # At col 0, can only go right
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 0)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert all(c >= 0 for _, c in move_targets)
        # left moves don't exist
        assert (3, -1) not in move_targets

    def test_no_moves_off_board(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 0, 0)
        for m in get_legal_moves(state):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8

    def test_can_reach_opponents_back_rank(self):
        # RED pokeball at row 6 can reach row 7
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 6, 3)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (7, 3) in move_targets

    def test_no_trade_for_pokeball(self):
        # Pokeballs cannot hold items and therefore cannot trade.
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 4)   # WATERSTONE
        pb_moves = moves_from(get_legal_moves(state), 3, 3)
        assert moves_of_type(pb_moves, ActionType.TRADE) == []


# ---------------------------------------------------------------------------
# TestMasterballMoves
# ---------------------------------------------------------------------------

class TestMasterballMoves:
    def test_open_center_move_count_red(self):
        # RED Masterball at (4,4): pokeball's 8 + backward 2 + backward-diag 2 = 12
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 12

    def test_has_backward_straight(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 4) in move_targets  # backward 1
        assert (2, 4) in move_targets  # backward 2

    def test_has_backward_diagonals(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 5) in move_targets  # backward-right diagonal
        assert (3, 3) in move_targets  # backward-left diagonal

    def test_retains_forward_moves(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (5, 4) in move_targets  # forward 1
        assert (6, 4) in move_targets  # forward 2
        assert (5, 5) in move_targets  # forward-right diagonal
        assert (5, 3) in move_targets  # forward-left diagonal

    def test_backward_blocked_at_1_prevents_reaching_2(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 4)  # friendly backward-1
        mb_moves = moves_from(get_legal_moves(state), 4, 4)
        move_targets = targets(moves_of_type(mb_moves, ActionType.MOVE))
        assert (3, 4) not in move_targets
        assert (2, 4) not in move_targets  # blocked

    def test_attacks_enemy_backward(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)  # enemy backward-1
        atk = moves_of_type(get_legal_moves(state), ActionType.ATTACK)
        assert any(m.target_row == 3 and m.target_col == 4 for m in atk)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (2, 4) not in move_targets  # blocked behind enemy

    def test_blue_masterball_backward_toward_high_rows(self):
        # BLUE forward = -row, so BLUE backward = +row
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.MASTERBALL, Team.BLUE, 4, 4)
        move_targets = targets(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert (3, 4) in move_targets   # BLUE forward
        assert (5, 4) in move_targets   # BLUE backward
        assert (6, 4) in move_targets   # BLUE backward 2

    def test_no_moves_off_board(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 0, 0)
        for m in get_legal_moves(state):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8


# ---------------------------------------------------------------------------
# TestKingMoves  (shared movement behaviour for all 8 king types)
# ---------------------------------------------------------------------------

class TestKingMoves:
    @pytest.mark.parametrize("pt", [
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE,
        PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    ])
    def test_open_center_move_count(self, pt):
        # All king types can reach all 8 adjacent squares from the center
        state = empty_state()
        place(state, pt, Team.RED, 4, 4)
        assert len(moves_of_type(get_legal_moves(state), ActionType.MOVE)) == 8

    @pytest.mark.parametrize("pt", [
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE,
        PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    ])
    def test_corner_limits_moves(self, pt):
        # From (0,0) only 3 adjacent squares are in bounds
        state = empty_state()
        place(state, pt, Team.RED, 0, 0)
        move_count = len(moves_of_type(get_legal_moves(state), ActionType.MOVE))
        assert move_count == 3

    @pytest.mark.parametrize("pt", [
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE,
        PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    ])
    def test_attacks_adjacent_enemy(self, pt):
        state = empty_state()
        place(state, pt, Team.RED, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 4, 5)
        atk = moves_of_type(moves_from(get_legal_moves(state), 4, 4), ActionType.ATTACK)
        assert any(m.target_row == 4 and m.target_col == 5 for m in atk)

    @pytest.mark.parametrize("pt", [
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE,
        PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    ])
    def test_does_not_attack_friendly(self, pt):
        state = empty_state()
        place(state, pt, Team.RED, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 5)
        king_moves = moves_from(get_legal_moves(state), 4, 4)
        # Friendly square must not appear in MOVE or ATTACK targets
        atk_and_move = moves_of_type(king_moves, ActionType.ATTACK) + moves_of_type(king_moves, ActionType.MOVE)
        assert (4, 5) not in targets(atk_and_move)

    @pytest.mark.parametrize("pt", [
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE,
        PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    ])
    def test_no_moves_off_board(self, pt):
        state = empty_state()
        place(state, pt, Team.RED, 0, 7)
        for m in moves_from(get_legal_moves(state), 0, 7):
            assert 0 <= m.target_row < 8 and 0 <= m.target_col < 8


# ---------------------------------------------------------------------------
# TestPikachuMoves
# ---------------------------------------------------------------------------

class TestPikachuMoves:
    def test_always_has_evolve(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        evos = moves_of_type(get_legal_moves(state), ActionType.EVOLVE)
        assert len(evos) == 1
        assert evos[0].target_row == 4 and evos[0].target_col == 4  # in-place

    def test_evolve_move_slot_is_none(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        evo = moves_of_type(get_legal_moves(state), ActionType.EVOLVE)[0]
        assert evo.move_slot is None

    def test_raichu_has_no_evolve(self):
        state = empty_state()
        place(state, PieceType.RAICHU, Team.RED, 4, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.EVOLVE) == []


# ---------------------------------------------------------------------------
# TestEeveeMoves
# ---------------------------------------------------------------------------

class TestEeveeMoves:
    def test_no_evolve_without_item(self):
        # Eevee starts with Item.NONE — no evolution available
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.EVOLVE) == []

    @pytest.mark.parametrize("item,expected_slot", [
        (Item.WATERSTONE,   0),
        (Item.FIRESTONE,    1),
        (Item.LEAFSTONE,    2),
        (Item.THUNDERSTONE, 3),
        (Item.BENTSPOON,    4),
    ])
    def test_evolve_slot_matches_item(self, item, expected_slot):
        state = empty_state(active=Team.BLUE)
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        eevee.held_item = item
        evos = moves_of_type(get_legal_moves(state), ActionType.EVOLVE)
        assert len(evos) == 1
        assert evos[0].move_slot == expected_slot
        assert evos[0].target_row == 4 and evos[0].target_col == 4  # in-place

    def test_one_evolve_per_item(self):
        # Holding a stone produces exactly one EVOLVE option
        state = empty_state(active=Team.BLUE)
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        eevee.held_item = Item.WATERSTONE
        assert len(moves_of_type(get_legal_moves(state), ActionType.EVOLVE)) == 1

    def test_quick_attack_no_enemies(self):
        # No enemies on the board → no Quick Attack moves
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK) == []

    def test_quick_attack_generated_for_enemy_in_range(self):
        # Enemy at (4,6) — 2 hops away; Eevee can move to (4,5) then attack (4,6)
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 6)
        qa = moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK)
        assert any(
            m.target_row == 4 and m.target_col == 5
            and m.secondary_row == 4 and m.secondary_col == 6
            for m in qa
        )

    def test_quick_attack_target_is_empty_destination(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        for m in moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK):
            dest = state.board[m.target_row][m.target_col]
            assert dest is None, "Quick Attack destination must be empty"

    def test_quick_attack_secondary_is_enemy(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        for m in moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK):
            target = state.board[m.secondary_row][m.secondary_col]
            assert target is not None and target.team != Team.BLUE

    def test_quick_attack_does_not_target_friendly(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.BULBASAUR, Team.BLUE, 5, 5)  # friendly
        assert moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK) == []

    def test_quick_attack_destination_cannot_be_occupied(self):
        # Friendly at (4,5) blocks that destination
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.BULBASAUR, Team.BLUE, 4, 5)   # blocks (4,5)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 6)     # enemy
        qa = moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK)
        # (4,5) occupied → no Quick Attack via (4,5)→(4,6)
        assert not any(m.target_row == 4 and m.target_col == 5 for m in qa)

    def test_quick_attack_secondary_fields_populated(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        for m in moves_of_type(get_legal_moves(state), ActionType.QUICK_ATTACK):
            assert m.secondary_row is not None and m.secondary_col is not None

    def test_standard_moves_and_quick_attack_coexist(self):
        # Eevee can both MOVE and QUICK_ATTACK — they're not mutually exclusive
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 6, 6)
        all_moves = get_legal_moves(state)
        assert len(moves_of_type(all_moves, ActionType.MOVE)) > 0
        assert len(moves_of_type(all_moves, ActionType.QUICK_ATTACK)) > 0


# ---------------------------------------------------------------------------
# TestEspeonMoves
# ---------------------------------------------------------------------------

class TestEspeonMoves:
    def test_foresight_targets_adjacent_squares(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        fs = moves_of_type(get_legal_moves(state), ActionType.FORESIGHT)
        # All 8 adjacent squares are valid foresight targets on an empty board
        assert len(fs) == 8

    def test_foresight_targets_only_adjacent(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        for m in moves_of_type(get_legal_moves(state), ActionType.FORESIGHT):
            dr = abs(m.target_row - 4)
            dc = abs(m.target_col - 4)
            assert max(dr, dc) == 1, "Espeon foresight must target adjacent squares only"

    def test_foresight_blocked_on_consecutive_turns(self):
        state = empty_state(active=Team.BLUE)
        state.foresight_used_last_turn[Team.BLUE] = True
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.FORESIGHT) == []

    def test_foresight_available_when_not_consecutive(self):
        state = empty_state(active=Team.BLUE)
        state.foresight_used_last_turn[Team.BLUE] = False
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        assert len(moves_of_type(get_legal_moves(state), ActionType.FORESIGHT)) > 0

    def test_foresight_excludes_friendly_squares(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.VAPOREON, Team.BLUE, 4, 5)  # friendly adjacent
        fs_targets = targets(moves_of_type(get_legal_moves(state), ActionType.FORESIGHT))
        assert (4, 5) not in fs_targets

    def test_foresight_includes_enemy_squares(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 5)  # enemy adjacent
        fs_targets = targets(moves_of_type(get_legal_moves(state), ActionType.FORESIGHT))
        assert (4, 5) in fs_targets

    def test_espeon_has_no_evolve(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        assert moves_of_type(get_legal_moves(state), ActionType.EVOLVE) == []
