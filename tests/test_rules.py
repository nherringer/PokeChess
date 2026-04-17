"""Tests for engine/rules.py — Task #6: move execution, damage, win conditions."""

import pytest
from engine import GameState, Piece, PieceType, Team, Item
from engine.moves import Move, ActionType
from engine.rules import apply_move, is_terminal, hp_winner
from engine.state import PIECE_STATS, ForesightEffect


# ---------------------------------------------------------------------------
# Board helpers (mirrors test_moves.py pattern)
# ---------------------------------------------------------------------------

def empty_state(active: Team = Team.RED, turn: int = 1) -> GameState:
    board = [[None] * 8 for _ in range(8)]
    return GameState(
        board=board,
        active_player=active,
        turn_number=turn,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def place(state: GameState, pt: PieceType, team: Team, row: int, col: int) -> Piece:
    piece = Piece.create(pt, team, row, col)
    state.board[row][col] = piece
    return piece


def make_move(pt: PieceType, pr: int, pc: int, at: ActionType,
              tr: int, tc: int, **kw) -> Move:
    return Move(piece_row=pr, piece_col=pc, action_type=at,
                target_row=tr, target_col=tc, **kw)


# ---------------------------------------------------------------------------
# TestTurnAdvancement
# ---------------------------------------------------------------------------

class TestTurnAdvancement:
    def test_red_move_switches_to_blue(self):
        state = empty_state(active=Team.RED, turn=1)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        move = make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 5)
        [(ns, _)] = apply_move(state, move)
        assert ns.active_player == Team.BLUE

    def test_blue_move_switches_to_red(self):
        state = empty_state(active=Team.BLUE, turn=2)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 3)
        move = make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 5)
        [(ns, _)] = apply_move(state, move)
        assert ns.active_player == Team.RED

    def test_turn_number_increments_each_half_move(self):
        state = empty_state(active=Team.RED, turn=1)
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 4))
        assert ns.turn_number == 2

    def test_original_state_unchanged(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 4))
        assert state.active_player == Team.RED
        assert state.turn_number == 1


# ---------------------------------------------------------------------------
# TestMoveAction
# ---------------------------------------------------------------------------

class TestMoveAction:
    def test_piece_appears_at_destination(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 6))
        assert ns.board[3][6] is not None
        assert ns.board[3][6].piece_type == PieceType.SQUIRTLE

    def test_origin_square_vacated(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 6))
        assert ns.board[3][3] is None

    def test_piece_row_col_updated(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 5, 3))
        piece = ns.board[5][3]
        assert piece.row == 5 and piece.col == 3

    def test_pokeball_promotion_at_back_rank(self):
        # RED pokeball reaching row 7 promotes to Masterball
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 6, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.POKEBALL, 6, 3, ActionType.MOVE, 7, 3))
        assert ns.board[7][3].piece_type == PieceType.MASTERBALL

    def test_blue_pokeball_promotion_at_row_0(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.POKEBALL, Team.BLUE, 1, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.POKEBALL, 1, 3, ActionType.MOVE, 0, 3))
        assert ns.board[0][3].piece_type == PieceType.MASTERBALL

    def test_pokeball_no_promotion_mid_board(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.MOVE, 4, 3))
        assert ns.board[4][3].piece_type == PieceType.POKEBALL


# ---------------------------------------------------------------------------
# TestAttackDamage
# ---------------------------------------------------------------------------

class TestAttackDamage:
    def test_neutral_damage_applied(self):
        # Squirtle (Water, 100 base) attacks Pikachu (Electric) — neutral 1.0× = 100
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        attacked = ns.board[3][4]
        assert attacked is not None
        assert attacked.current_hp == PIECE_STATS[PieceType.PIKACHU].max_hp - 100

    def test_super_effective_damage(self):
        # Squirtle (Water, 100 base) vs Charmander (Fire) — 2.0× = 200
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        # 200 damage = KO; Squirtle captures the square
        assert ns.board[3][4].piece_type == PieceType.SQUIRTLE

    def test_not_very_effective_damage(self):
        # Squirtle (Water, 100 base) vs Bulbasaur (Grass) — 0.5× = 50
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.BULBASAUR, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        assert ns.board[3][4].current_hp == 200 - 50

    def test_attacker_stays_when_target_survives(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        assert ns.board[3][3] is not None  # attacker still at origin
        assert ns.board[3][3].piece_type == PieceType.SQUIRTLE

    def test_attacker_captures_square_on_ko(self):
        # Give target just enough HP to be KO'd in one hit
        state = empty_state()
        attacker = place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        target = place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        target.current_hp = 100  # will take 200 damage (2× super effective) → KO
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        assert ns.board[3][3] is None           # origin vacated
        assert ns.board[3][4] is not None       # target square now has attacker
        assert ns.board[3][4].piece_type == PieceType.SQUIRTLE

    def test_ko_target_removed_from_board(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        target = place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        target.current_hp = 10
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        assert ns.board[3][4].team == Team.RED  # attacker now there, not the Blue piece

    def test_mew_slot_0_fire_blast_neutral(self):
        # Mew slot 0 = Fire Blast (FIRE, 100 base) vs Pikachu (Electric) — neutral 1.0× = 100
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.ATTACK, 3, 4, move_slot=0))
        assert ns.board[3][4].current_hp == 200 - 100

    def test_mew_slot_0_fire_blast_supereffective(self):
        # Mew Fire Blast (FIRE, 100 base) vs Bulbasaur (Grass) — 2.0× = 200 → KO
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.BULBASAUR, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.ATTACK, 3, 4, move_slot=0))
        assert ns.board[3][4].piece_type == PieceType.MEW

    def test_mew_slot_1_hydro_pump_supereffective(self):
        # Mew Hydro Pump (WATER, 100 base) vs Charmander (Fire) — 2.0× = 200 → KO
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.ATTACK, 3, 4, move_slot=1))
        assert ns.board[3][4].piece_type == PieceType.MEW

    def test_mew_slot_2_solar_beam_supereffective(self):
        # Mew Solar Beam (GRASS, 100 base) vs Squirtle (Water) — 2.0× = 200 → KO
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.ATTACK, 3, 4, move_slot=2))
        assert ns.board[3][4].piece_type == PieceType.MEW

    def test_mew_nonlethal_stays_put(self):
        # Mew Fire Blast (FIRE, 100 base) vs Squirtle (Water) — 0.5× = 50, no KO → Mew stays
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.ATTACK, 3, 4, move_slot=0))
        assert ns.board[3][3].piece_type == PieceType.MEW  # stayed in place
        assert ns.board[3][4].current_hp == 200 - 50

    def test_held_item_does_not_affect_damage(self):
        # Items are only for evolution — held item must not change damage output.
        # Squirtle (Water, 100 base) + WATERSTONE vs Charmander (Fire): 2.0× = 200 → KO.
        state = empty_state()
        attacker = place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        attacker.held_item = Item.WATERSTONE
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        # KO: Squirtle captures the square (same result with or without WATERSTONE)
        assert ns.board[3][4].piece_type == PieceType.SQUIRTLE

    def test_attacker_position_updated_after_capture(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        target = place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        target.current_hp = 10
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.ATTACK, 3, 4))
        captured_piece = ns.board[3][4]
        assert captured_piece.row == 3 and captured_piece.col == 4


# ---------------------------------------------------------------------------
# TestPokeballCapture
# ---------------------------------------------------------------------------

class TestPokeballCapture:
    def test_returns_two_outcomes(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert len(results) == 2

    def test_probabilities_sum_to_one(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert abs(sum(p for _, p in results) - 1.0) < 1e-9

    def test_each_probability_is_half(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        probs = sorted(p for _, p in results)
        assert probs == [0.5, 0.5]

    def test_capture_state_both_removed(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        # Capture: both pokeball (3,3) and target (3,4) are removed
        capture_states = [s for s, _ in results if s.board[3][3] is None and s.board[3][4] is None]
        # Fail: pokeball consumed (3,3 empty), target survives (3,4 has Squirtle)
        fail_states    = [s for s, _ in results if s.board[3][3] is None
                          and s.board[3][4] is not None and s.board[3][4].team == Team.BLUE]
        assert len(capture_states) == 1
        assert len(fail_states) == 1

    def test_fail_state_pokeball_consumed(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        fail_states = [s for s, _ in results if s.board[3][4] is not None and s.board[3][4].team == Team.BLUE]
        fail = fail_states[0]
        # Pokeball is consumed (thrown and missed) — gone from its original square
        assert fail.board[3][3] is None

    def test_pikachu_immune_returns_one_outcome(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert len(results) == 1

    def test_pikachu_immune_not_captured(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        [(ns, p)] = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert p == 1.0
        assert ns.board[3][4].piece_type == PieceType.PIKACHU  # still there
        assert ns.board[3][3].piece_type == PieceType.POKEBALL  # pokeball stays

    def test_raichu_not_immune(self):
        # Raichu loses Pikachu's immunity after evolution — pokeball can attempt capture
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.RAICHU, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.POKEBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert len(results) == 2  # stochastic: 50% catch, 50% fail
        probs = sorted(p for _, p in results)
        assert probs == [0.5, 0.5]


# ---------------------------------------------------------------------------
# TestMasterballCapture
# ---------------------------------------------------------------------------

class TestMasterballCapture:
    def test_guaranteed_capture(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, make_move(PieceType.MASTERBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert len(results) == 1
        [(ns, p)] = results
        assert p == 1.0
        # Masterball is consumed on use — both pieces gone
        assert ns.board[3][3] is None
        assert ns.board[3][4] is None

    def test_masterball_can_capture_pikachu(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        [(ns, p)] = apply_move(state, make_move(PieceType.MASTERBALL, 3, 3, ActionType.ATTACK, 3, 4))
        assert p == 1.0
        # Masterball is consumed on use — both pieces gone
        assert ns.board[3][3] is None
        assert ns.board[3][4] is None


# ---------------------------------------------------------------------------
# TestForesight
# ---------------------------------------------------------------------------

class TestForesight:
    def test_schedules_foresight_effect(self):
        state = empty_state(turn=1)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        move = make_move(PieceType.MEW, 3, 3, ActionType.FORESIGHT, 5, 5)
        [(ns, _)] = apply_move(state, move)
        fx = ns.pending_foresight[Team.RED]
        assert fx is not None
        assert fx.target_row == 5 and fx.target_col == 5

    def test_foresight_resolves_on_correct_turn(self):
        state = empty_state(turn=1)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.FORESIGHT, 5, 5))
        assert ns.pending_foresight[Team.RED].resolves_on_turn == 3  # turn 1 + 2

    def test_foresight_used_last_turn_set(self):
        state = empty_state(turn=1)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.FORESIGHT, 5, 5))
        assert ns.foresight_used_last_turn[Team.RED] is True

    def test_foresight_resolves_and_deals_damage(self):
        # Mew casts Foresight on turn 1 targeting (5,5).
        # Simulate RED's turn 3 (when it resolves).
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        target = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=5, target_col=5, damage=120, resolves_on_turn=3,
        )
        # Make any non-Foresight move to trigger resolution
        move = make_move(PieceType.MEW, 3, 3, ActionType.MOVE, 3, 4)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[5][5].current_hp == 200 - 120

    def test_foresight_ko_removes_piece(self):
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        target = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        target.current_hp = 100
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=5, target_col=5, damage=120, resolves_on_turn=3,
        )
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.MOVE, 3, 4))
        assert ns.board[5][5] is None  # KO'd by Foresight

    def test_foresight_clears_after_resolution(self):
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=5, target_col=5, damage=120, resolves_on_turn=3,
        )
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.MOVE, 3, 4))
        assert ns.pending_foresight[Team.RED] is None

    def test_foresight_misses_empty_square(self):
        # Target square is empty at resolution — no crash, nothing happens
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 3, 3)
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=5, target_col=5, damage=120, resolves_on_turn=3,
        )
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.MOVE, 3, 4))
        assert ns.board[5][5] is None  # was empty, stays empty


# ---------------------------------------------------------------------------
# TestTradeAction
# ---------------------------------------------------------------------------

class TestTradeAction:
    def test_items_swapped(self):
        state = empty_state()
        a = place(state, PieceType.SQUIRTLE,   Team.RED, 3, 3)  # WATERSTONE
        b = place(state, PieceType.CHARMANDER, Team.RED, 3, 4)  # FIRESTONE
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4))
        pa = ns.board[3][3]
        pb = ns.board[3][4]
        assert pa.held_item == Item.FIRESTONE
        assert pb.held_item == Item.WATERSTONE

    def test_both_pieces_remain_on_board(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE,   Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.RED, 3, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4))
        assert ns.board[3][3] is not None
        assert ns.board[3][4] is not None

    def test_trade_does_not_advance_turn(self):
        # Regular TRADE is a free action — active player stays the same
        state = empty_state(active=Team.RED)
        place(state, PieceType.SQUIRTLE,   Team.RED, 3, 3)  # WATERSTONE
        place(state, PieceType.CHARMANDER, Team.RED, 3, 4)  # FIRESTONE
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4))
        assert ns.active_player == Team.RED

    def test_trade_sets_has_traded_flag(self):
        state = empty_state(active=Team.RED)
        place(state, PieceType.SQUIRTLE,   Team.RED, 3, 3)  # WATERSTONE
        place(state, PieceType.CHARMANDER, Team.RED, 3, 4)  # FIRESTONE
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4))
        assert ns.has_traded[Team.RED] is True

    def test_eevee_trade_receives_stone_but_does_not_auto_evolve(self):
        # Eevee receiving an evolution stone via TRADE now holds it as a held item.
        # Auto-evolution was removed — the player must trigger EVOLVE explicitly.
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 3)  # holds WATERSTONE
        place(state, PieceType.EEVEE,    Team.BLUE, 3, 4)  # holds NONE
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4))
        # Eevee still Eevee — no auto-evolution
        assert ns.board[3][4].piece_type == PieceType.EEVEE
        # Eevee now holds the Waterstone (stone not consumed)
        assert ns.board[3][4].held_item == Item.WATERSTONE
        # Trade is a free action — turn does NOT advance (still BLUE's turn)
        assert ns.active_player == Team.BLUE


# ---------------------------------------------------------------------------
# TestEvolveAction
# ---------------------------------------------------------------------------

class TestEvolveAction:
    def test_pikachu_becomes_raichu(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4))
        assert ns.board[4][4].piece_type == PieceType.RAICHU

    def test_pikachu_thunderstone_consumed(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4))
        assert ns.board[4][4].held_item == Item.NONE

    def test_pikachu_full_hp_gains_delta_on_evolve(self):
        # Pikachu (200 max) → Raichu (250 max): +50 HP gain
        state = empty_state()
        pikachu = place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        pikachu.current_hp = 200  # full HP
        [(ns, _)] = apply_move(state, make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4))
        assert ns.board[4][4].current_hp == 250  # 200 + 50 = 250 (at new max)

    def test_pikachu_damaged_gains_delta_on_evolve(self):
        # Injured Pikachu at 120 HP gains +50 → 170 HP after evolving
        state = empty_state()
        pikachu = place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        pikachu.current_hp = 120
        [(ns, _)] = apply_move(state, make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4))
        assert ns.board[4][4].current_hp == 170  # 120 + 50

    @pytest.mark.parametrize("item,expected_slot,expected_type", [
        (Item.WATERSTONE,   0, PieceType.VAPOREON),
        (Item.FIRESTONE,    1, PieceType.FLAREON),
        (Item.LEAFSTONE,    2, PieceType.LEAFEON),
        (Item.THUNDERSTONE, 3, PieceType.JOLTEON),
        (Item.BENTSPOON,    4, PieceType.ESPEON),
    ])
    def test_eevee_evolution(self, item, expected_slot, expected_type):
        state = empty_state(active=Team.BLUE)
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        eevee.held_item = item
        [(ns, _)] = apply_move(state, make_move(
            PieceType.EEVEE, 4, 4, ActionType.EVOLVE, 4, 4, move_slot=expected_slot
        ))
        assert ns.board[4][4].piece_type == expected_type

    def test_eevee_stone_consumed_on_evolution(self):
        state = empty_state(active=Team.BLUE)
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        eevee.held_item = Item.WATERSTONE
        [(ns, _)] = apply_move(state, make_move(
            PieceType.EEVEE, 4, 4, ActionType.EVOLVE, 4, 4, move_slot=0
        ))
        assert ns.board[4][4].held_item == Item.NONE

    def test_evolution_stays_in_place(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        [(ns, _)] = apply_move(state, make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4))
        assert ns.board[4][4] is not None
        assert ns.board[4][4].row == 4 and ns.board[4][4].col == 4


# ---------------------------------------------------------------------------
# TestQuickAttack
# ---------------------------------------------------------------------------

class TestQuickAttack:
    def test_eevee_vacates_original_square(self):
        # Eevee attacks adjacent enemy (5,5), no KO; then moves to (4,5).
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        # target=(5,5) attack; secondary=(4,5) movement
        move = Move(4, 4, ActionType.QUICK_ATTACK, 5, 5,
                    secondary_row=4, secondary_col=5)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[4][4] is None  # original square vacated

    def test_quick_attack_deals_damage(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        # Attack (5,5) directly [adjacent diag]; move to (4,5) after
        move = Move(4, 4, ActionType.QUICK_ATTACK, 5, 5,
                    secondary_row=4, secondary_col=5)
        [(ns, _)] = apply_move(state, move)
        # Eevee (Normal, 50 base) vs Squirtle (Water) = 1.0× → 50 damage
        assert ns.board[5][5].current_hp == 200 - 50

    def test_quick_attack_ko_eevee_captures(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.EEVEE, Team.BLUE, 4, 4)
        target = place(state, PieceType.SQUIRTLE, Team.RED, 5, 5)
        target.current_hp = 10  # will be KO'd by 50 base damage
        # Attack (5,5) → KO; Eevee occupies (5,5); then moves to (5,6)
        move = Move(4, 4, ActionType.QUICK_ATTACK, 5, 5,
                    secondary_row=5, secondary_col=6)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[4][4] is None              # original square vacated
        assert ns.board[5][5] is None              # KO target; Eevee moved on
        assert ns.board[5][6].team == Team.BLUE    # Eevee at secondary destination


# ---------------------------------------------------------------------------
# TestIsTerminal
# ---------------------------------------------------------------------------

class TestIsTerminal:
    def test_both_kings_alive_not_terminal(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED,  0, 4)
        place(state, PieceType.EEVEE,   Team.BLUE, 7, 4)
        done, winner = is_terminal(state)
        assert done is False
        assert winner is None

    def test_red_king_gone_blue_wins(self):
        state = empty_state()
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        done, winner = is_terminal(state)
        assert done is True
        assert winner == Team.BLUE

    def test_blue_king_gone_red_wins(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        done, winner = is_terminal(state)
        assert done is True
        assert winner == Team.RED

    def test_both_kings_gone_draw(self):
        done, winner = is_terminal(empty_state())
        assert done is True
        assert winner is None

    def test_evolved_king_counts(self):
        # Raichu is still a king — game not over if it's alive
        state = empty_state()
        place(state, PieceType.RAICHU,  Team.RED,  0, 4)
        place(state, PieceType.VAPOREON, Team.BLUE, 7, 4)
        done, _ = is_terminal(state)
        assert done is False

    def test_non_king_pieces_dont_end_game(self):
        state = empty_state()
        place(state, PieceType.PIKACHU,  Team.RED,  0, 4)
        place(state, PieceType.EEVEE,    Team.BLUE, 7, 4)
        place(state, PieceType.SQUIRTLE, Team.RED,  3, 3)
        done, _ = is_terminal(state)
        assert done is False


# ---------------------------------------------------------------------------
# TestHpWinner
# ---------------------------------------------------------------------------

class TestHpWinner:
    def test_red_leads_wins(self):
        state = empty_state()
        r = place(state, PieceType.SQUIRTLE, Team.RED,  3, 3)
        b = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        r.current_hp = 200
        b.current_hp = 100
        assert hp_winner(state) == Team.RED

    def test_blue_leads_wins(self):
        state = empty_state()
        r = place(state, PieceType.SQUIRTLE, Team.RED,  3, 3)
        b = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        r.current_hp = 50
        b.current_hp = 180
        assert hp_winner(state) == Team.BLUE

    def test_tied_hp_returns_none(self):
        state = empty_state()
        r = place(state, PieceType.SQUIRTLE, Team.RED,  3, 3)
        b = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        r.current_hp = 100
        b.current_hp = 100
        assert hp_winner(state) is None

    def test_sums_across_all_pieces(self):
        state = empty_state()
        for col in range(3):
            p = place(state, PieceType.SQUIRTLE, Team.RED,  1, col)
            p.current_hp = 100
        b = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        b.current_hp = 200
        # RED total = 300, BLUE total = 200
        assert hp_winner(state) == Team.RED

    def test_pokeball_counts_as_50(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED,  1, 0)  # counts 50
        b = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 5)
        b.current_hp = 40  # BLUE = 40, RED = 50 → RED wins
        assert hp_winner(state) == Team.RED

    def test_masterball_counts_as_200(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.BLUE, 6, 0)  # counts 200
        r = place(state, PieceType.SQUIRTLE, Team.RED, 1, 0)
        r.current_hp = 150  # RED = 150, BLUE = 200 → BLUE wins
        assert hp_winner(state) == Team.BLUE


# ---------------------------------------------------------------------------
# TestForesightFlag
# ---------------------------------------------------------------------------

class TestForesightFlag:
    def test_non_foresight_move_resets_flag(self):
        state = empty_state()
        state.foresight_used_last_turn[Team.RED] = True
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.SQUIRTLE, 3, 3, ActionType.MOVE, 3, 4))
        assert ns.foresight_used_last_turn[Team.RED] is False

    def test_foresight_move_sets_flag(self):
        state = empty_state()
        place(state, PieceType.MEW, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.FORESIGHT, 5, 5))
        assert ns.foresight_used_last_turn[Team.RED] is True

    def test_opponent_flag_unaffected(self):
        state = empty_state()
        state.foresight_used_last_turn[Team.BLUE] = True
        place(state, PieceType.MEW, Team.RED, 3, 3)
        [(ns, _)] = apply_move(state, make_move(PieceType.MEW, 3, 3, ActionType.FORESIGHT, 5, 5))
        assert ns.foresight_used_last_turn[Team.BLUE] is True  # unchanged
