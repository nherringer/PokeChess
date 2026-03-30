"""Tests for engine/state.py — GameState, Piece, and all supporting data."""
import dataclasses
import pytest

from engine.state import (
    GameState, Piece, ForesightEffect,
    PieceType, PokemonType, Team, Item,
    PIECE_STATS, KING_TYPES, PAWN_TYPES, MATCHUP,
)


# ---------------------------------------------------------------------------
# PIECE_STATS completeness and correctness
# ---------------------------------------------------------------------------

class TestPieceStats:
    def test_every_piece_type_has_entry(self):
        for pt in PieceType:
            assert pt in PIECE_STATS, f"{pt} missing from PIECE_STATS"

    def test_hp_always_multiple_of_ten(self):
        for pt, stats in PIECE_STATS.items():
            assert stats.max_hp % 10 == 0, f"{pt} HP {stats.max_hp} not multiple of 10"

    def test_pokeball_has_zero_hp(self):
        assert PIECE_STATS[PieceType.POKEBALL].max_hp == 0
        assert PIECE_STATS[PieceType.MASTERBALL].max_hp == 0

    def test_known_hp_values(self):
        expected = {
            PieceType.SQUIRTLE:   200,
            PieceType.CHARMANDER: 200,
            PieceType.BULBASAUR:  200,
            PieceType.MEW:        250,
            PieceType.PIKACHU:    200,
            PieceType.RAICHU:     250,
            PieceType.EEVEE:      120,
            PieceType.VAPOREON:   220,
            PieceType.FLAREON:    220,
            PieceType.LEAFEON:    220,
            PieceType.JOLTEON:    220,
            PieceType.ESPEON:     220,
        }
        for pt, hp in expected.items():
            assert PIECE_STATS[pt].max_hp == hp, f"{pt}: expected {hp}, got {PIECE_STATS[pt].max_hp}"

    def test_known_types(self):
        expected = {
            PieceType.SQUIRTLE:   PokemonType.WATER,
            PieceType.CHARMANDER: PokemonType.FIRE,
            PieceType.BULBASAUR:  PokemonType.GRASS,
            PieceType.MEW:        PokemonType.PSYCHIC,
            PieceType.PIKACHU:    PokemonType.ELECTRIC,
            PieceType.RAICHU:     PokemonType.ELECTRIC,
            PieceType.EEVEE:      PokemonType.NORMAL,
            PieceType.VAPOREON:   PokemonType.WATER,
            PieceType.FLAREON:    PokemonType.FIRE,
            PieceType.LEAFEON:    PokemonType.GRASS,
            PieceType.JOLTEON:    PokemonType.ELECTRIC,
            PieceType.ESPEON:     PokemonType.PSYCHIC,
            PieceType.POKEBALL:   PokemonType.NONE,
            PieceType.MASTERBALL: PokemonType.NONE,
        }
        for pt, ptype in expected.items():
            assert PIECE_STATS[pt].pokemon_type == ptype

    def test_known_default_items(self):
        expected = {
            PieceType.SQUIRTLE:   Item.WATERSTONE,
            PieceType.CHARMANDER: Item.FIRESTONE,
            PieceType.BULBASAUR:  Item.LEAFSTONE,
            PieceType.MEW:        Item.BENTSPOON,
            PieceType.PIKACHU:    Item.THUNDERSTONE,
            PieceType.RAICHU:     Item.NONE,
            PieceType.EEVEE:      Item.NONE,
            PieceType.POKEBALL:   Item.NONE,
            PieceType.MASTERBALL: Item.NONE,
        }
        for pt, item in expected.items():
            assert PIECE_STATS[pt].default_item == item


# ---------------------------------------------------------------------------
# KING_TYPES and PAWN_TYPES classification
# ---------------------------------------------------------------------------

class TestPieceClassification:
    KING_PIECE_TYPES = {
        PieceType.PIKACHU, PieceType.RAICHU,
        PieceType.EEVEE, PieceType.VAPOREON, PieceType.FLAREON,
        PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
    }
    PAWN_PIECE_TYPES = {
        PieceType.POKEBALL, PieceType.MASTERBALL,
        PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL,
    }

    def test_king_types_set(self):
        assert KING_TYPES == self.KING_PIECE_TYPES

    def test_pawn_types_set(self):
        assert PAWN_TYPES == self.PAWN_PIECE_TYPES

    def test_king_types_are_disjoint_from_pawn_types(self):
        assert KING_TYPES.isdisjoint(PAWN_TYPES)

    @pytest.mark.parametrize("pt", list(KING_PIECE_TYPES))
    def test_is_king_true(self, pt):
        piece = Piece.create(pt, Team.RED, 0, 4)
        assert piece.is_king

    @pytest.mark.parametrize("pt", [
        PieceType.SQUIRTLE, PieceType.CHARMANDER, PieceType.BULBASAUR,
        PieceType.MEW, PieceType.POKEBALL, PieceType.MASTERBALL,
    ])
    def test_is_king_false(self, pt):
        piece = Piece.create(pt, Team.RED, 0, 0)
        assert not piece.is_king

    @pytest.mark.parametrize("pt", [PieceType.POKEBALL, PieceType.MASTERBALL])
    def test_is_pawn_true(self, pt):
        piece = Piece.create(pt, Team.RED, 1, 0)
        assert piece.is_pawn

    @pytest.mark.parametrize("pt", [
        PieceType.SQUIRTLE, PieceType.CHARMANDER, PieceType.BULBASAUR,
        PieceType.MEW, PieceType.PIKACHU, PieceType.EEVEE,
    ])
    def test_is_pawn_false(self, pt):
        piece = Piece.create(pt, Team.RED, 0, 0)
        assert not piece.is_pawn


# ---------------------------------------------------------------------------
# MATCHUP table
# ---------------------------------------------------------------------------

class TestMatchup:
    def test_every_type_has_row(self):
        for pt in PokemonType:
            assert pt in MATCHUP, f"{pt} missing from MATCHUP"

    def test_every_row_has_all_columns(self):
        for attacker, row in MATCHUP.items():
            for defender in PokemonType:
                assert defender in row, f"MATCHUP[{attacker}][{defender}] missing"

    def test_starter_super_effective(self):
        assert MATCHUP[PokemonType.WATER][PokemonType.FIRE] == 2.0
        assert MATCHUP[PokemonType.FIRE][PokemonType.GRASS] == 2.0
        assert MATCHUP[PokemonType.GRASS][PokemonType.WATER] == 2.0

    def test_starter_not_very_effective(self):
        assert MATCHUP[PokemonType.WATER][PokemonType.GRASS] == 0.5
        assert MATCHUP[PokemonType.FIRE][PokemonType.WATER] == 0.5
        assert MATCHUP[PokemonType.GRASS][PokemonType.FIRE] == 0.5

    def test_same_type_resisted(self):
        for pt in [PokemonType.WATER, PokemonType.FIRE, PokemonType.GRASS]:
            assert MATCHUP[pt][pt] == 0.5

    def test_none_type_always_neutral(self):
        for defender in PokemonType:
            assert MATCHUP[PokemonType.NONE][defender] == 1.0
        for attacker in PokemonType:
            assert MATCHUP[attacker][PokemonType.NONE] == 1.0

    def test_all_multipliers_are_valid(self):
        valid = {0.5, 1.0, 2.0}
        for attacker, row in MATCHUP.items():
            for defender, mult in row.items():
                assert mult in valid, f"MATCHUP[{attacker}][{defender}] = {mult}"


# ---------------------------------------------------------------------------
# Piece.create and properties
# ---------------------------------------------------------------------------

class TestPieceCreate:
    def test_creates_with_full_hp(self):
        piece = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        assert piece.current_hp == 200
        assert piece.max_hp == 200

    def test_creates_with_default_item(self):
        piece = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        assert piece.held_item == Item.WATERSTONE

    def test_position_stored(self):
        piece = Piece.create(PieceType.MEW, Team.BLUE, 7, 3)
        assert piece.row == 7
        assert piece.col == 3

    def test_team_stored(self):
        red = Piece.create(PieceType.PIKACHU, Team.RED, 0, 4)
        blue = Piece.create(PieceType.EEVEE, Team.BLUE, 7, 4)
        assert red.team == Team.RED
        assert blue.team == Team.BLUE

    def test_pokemon_type_property(self):
        assert Piece.create(PieceType.SQUIRTLE,   Team.RED, 0, 0).pokemon_type == PokemonType.WATER
        assert Piece.create(PieceType.CHARMANDER, Team.RED, 0, 1).pokemon_type == PokemonType.FIRE
        assert Piece.create(PieceType.BULBASAUR,  Team.RED, 0, 2).pokemon_type == PokemonType.GRASS
        assert Piece.create(PieceType.MEW,         Team.RED, 0, 3).pokemon_type == PokemonType.PSYCHIC
        assert Piece.create(PieceType.PIKACHU,     Team.RED, 0, 4).pokemon_type == PokemonType.ELECTRIC
        assert Piece.create(PieceType.EEVEE,       Team.BLUE, 7, 4).pokemon_type == PokemonType.NORMAL

    def test_eevee_starts_with_no_item(self):
        piece = Piece.create(PieceType.EEVEE, Team.BLUE, 7, 4)
        assert piece.held_item == Item.NONE

    def test_pokeball_zero_hp(self):
        piece = Piece.create(PieceType.POKEBALL, Team.RED, 1, 0)
        assert piece.current_hp == 0
        assert piece.max_hp == 0


# ---------------------------------------------------------------------------
# Piece.copy
# ---------------------------------------------------------------------------

class TestPieceCopy:
    def test_copy_equals_original(self):
        piece = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        copy = piece.copy()
        assert copy == piece

    def test_copy_is_independent(self):
        piece = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        copy = piece.copy()
        copy.current_hp = 50
        assert piece.current_hp == 200

    def test_copy_item_independent(self):
        piece = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        copy = piece.copy()
        copy.held_item = Item.NONE
        assert piece.held_item == Item.WATERSTONE


# ---------------------------------------------------------------------------
# GameState.new_game — starting position
# ---------------------------------------------------------------------------

class TestNewGame:
    @pytest.fixture
    def state(self):
        return GameState.new_game()

    def test_red_moves_first(self, state):
        assert state.active_player == Team.RED

    def test_turn_one(self, state):
        assert state.turn_number == 1

    def test_no_pending_foresight(self, state):
        assert state.pending_foresight[Team.RED] is None
        assert state.pending_foresight[Team.BLUE] is None

    def test_foresight_flags_clear(self, state):
        assert state.foresight_used_last_turn[Team.RED] is False
        assert state.foresight_used_last_turn[Team.BLUE] is False

    def test_total_piece_count(self, state):
        assert len(state.all_pieces()) == 32

    def test_each_team_has_sixteen_pieces(self, state):
        assert len(state.all_pieces(Team.RED)) == 16
        assert len(state.all_pieces(Team.BLUE)) == 16

    def test_each_team_has_four_pokeballs_and_four_safetyballs(self, state):
        for team in Team:
            stealballs = [p for p in state.all_pieces(team) if p.piece_type == PieceType.POKEBALL]
            safetyballs = [p for p in state.all_pieces(team) if p.piece_type == PieceType.SAFETYBALL]
            assert len(stealballs) == 4
            assert len(safetyballs) == 4

    def test_middle_rows_empty(self, state):
        for row in range(2, 6):
            for col in range(8):
                assert state.piece_at(row, col) is None

    # --- Red back rank (row 0) ---
    @pytest.mark.parametrize("col,expected_type", [
        (0, PieceType.SQUIRTLE),
        (1, PieceType.CHARMANDER),
        (2, PieceType.BULBASAUR),
        (3, PieceType.MEW),
        (4, PieceType.PIKACHU),
        (5, PieceType.BULBASAUR),
        (6, PieceType.CHARMANDER),
        (7, PieceType.SQUIRTLE),
    ])
    def test_red_back_rank(self, state, col, expected_type):
        piece = state.piece_at(0, col)
        assert piece is not None
        assert piece.piece_type == expected_type
        assert piece.team == Team.RED

    # --- Blue back rank (row 7) ---
    @pytest.mark.parametrize("col,expected_type", [
        (0, PieceType.SQUIRTLE),
        (1, PieceType.CHARMANDER),
        (2, PieceType.BULBASAUR),
        (3, PieceType.MEW),
        (4, PieceType.EEVEE),
        (5, PieceType.BULBASAUR),
        (6, PieceType.CHARMANDER),
        (7, PieceType.SQUIRTLE),
    ])
    def test_blue_back_rank(self, state, col, expected_type):
        piece = state.piece_at(7, col)
        assert piece is not None
        assert piece.piece_type == expected_type
        assert piece.team == Team.BLUE

    def test_red_pawn_rank(self, state):
        # Even cols = Stealball (POKEBALL), odd cols = Safetyball (alternating pattern)
        for col in range(8):
            piece = state.piece_at(1, col)
            assert piece is not None
            expected = PieceType.POKEBALL if col % 2 == 0 else PieceType.SAFETYBALL
            assert piece.piece_type == expected
            assert piece.team == Team.RED

    def test_blue_pawn_rank(self, state):
        for col in range(8):
            piece = state.piece_at(6, col)
            assert piece is not None
            expected = PieceType.POKEBALL if col % 2 == 0 else PieceType.SAFETYBALL
            assert piece.piece_type == expected
            assert piece.team == Team.BLUE

    def test_all_pieces_start_at_full_hp(self, state):
        for piece in state.all_pieces():
            assert piece.current_hp == piece.max_hp

    def test_all_pieces_have_default_items(self, state):
        for piece in state.all_pieces():
            assert piece.held_item == PIECE_STATS[piece.piece_type].default_item


# ---------------------------------------------------------------------------
# GameState.piece_at
# ---------------------------------------------------------------------------

class TestPieceAt:
    def test_returns_piece_at_occupied_square(self):
        state = GameState.new_game()
        assert state.piece_at(0, 4).piece_type == PieceType.PIKACHU

    def test_returns_none_at_empty_square(self):
        state = GameState.new_game()
        assert state.piece_at(3, 3) is None


# ---------------------------------------------------------------------------
# GameState.all_pieces
# ---------------------------------------------------------------------------

class TestAllPieces:
    @pytest.fixture
    def state(self):
        return GameState.new_game()

    def test_no_filter_returns_all(self, state):
        assert len(state.all_pieces()) == 32

    def test_red_filter(self, state):
        red = state.all_pieces(Team.RED)
        assert len(red) == 16
        assert all(p.team == Team.RED for p in red)

    def test_blue_filter(self, state):
        blue = state.all_pieces(Team.BLUE)
        assert len(blue) == 16
        assert all(p.team == Team.BLUE for p in blue)

    def test_no_nones_in_result(self, state):
        assert all(p is not None for p in state.all_pieces())


# ---------------------------------------------------------------------------
# GameState.copy — deep copy correctness
# ---------------------------------------------------------------------------

class TestGameStateCopy:
    @pytest.fixture
    def state(self):
        return GameState.new_game()

    def test_copy_has_same_active_player(self, state):
        assert state.copy().active_player == Team.RED

    def test_copy_has_same_turn_number(self, state):
        assert state.copy().turn_number == 1

    def test_mutating_piece_hp_in_copy_does_not_affect_original(self, state):
        copy = state.copy()
        copy.board[0][0].current_hp = 50
        assert state.board[0][0].current_hp == 200

    def test_mutating_piece_item_in_copy_does_not_affect_original(self, state):
        copy = state.copy()
        copy.board[0][0].held_item = Item.NONE
        assert state.board[0][0].held_item == Item.WATERSTONE

    def test_removing_piece_from_copy_does_not_affect_original(self, state):
        copy = state.copy()
        copy.board[0][0] = None
        assert state.board[0][0] is not None

    def test_mutating_foresight_flag_in_copy_does_not_affect_original(self, state):
        copy = state.copy()
        copy.foresight_used_last_turn[Team.RED] = True
        assert state.foresight_used_last_turn[Team.RED] is False

    def test_mutating_pending_foresight_in_copy_does_not_affect_original(self, state):
        fx = ForesightEffect(target_row=3, target_col=3, damage=120, resolves_on_turn=3)
        copy = state.copy()
        copy.pending_foresight[Team.RED] = fx
        assert state.pending_foresight[Team.RED] is None

    def test_foresight_effect_deep_copied(self, state):
        fx = ForesightEffect(target_row=3, target_col=3, damage=120, resolves_on_turn=3)
        state.pending_foresight[Team.RED] = fx
        copy = state.copy()
        copy.pending_foresight[Team.RED].damage = 999
        assert state.pending_foresight[Team.RED].damage == 120
