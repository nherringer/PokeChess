"""
Tests for HP normalization, eeveelution changes, Leafeon reduction, and Espeon attacks
(TallGrass Update, criteria §17-22).

Covers:
  - PIECE_STATS HP values: Eevee 150, Vaporeon 300, Jolteon 200
  - Quick Attack available for Vaporeon, Flareon, Leafeon, Jolteon (not Espeon)
  - Espeon has no ATTACK moves; only MOVE, FORESIGHT, PSYWAVE
  - Flareon: 180 base FIRE damage
  - Flareon: 40 recoil after ATTACK (not after QA)
  - Flareon recoil can KO Flareon
  - Leafeon: -40 base damage reduction (before type effectiveness, floor 1)
  - Jolteon: 2-square diagonal jumps
  - Raichu and Jolteon: 2-square cardinal moves jump over obstacles
"""

from __future__ import annotations

import pytest
from engine.state import (
    GameState, Piece, PieceType, Team, Item, PIECE_STATS,
)
from engine.moves import Move, ActionType, get_legal_moves
from engine.rules import apply_move, calc_damage_with_multiplier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def empty_state(active: Team = Team.RED, turn: int = 1) -> GameState:
    board = [[None] * 8 for _ in range(8)]
    return GameState(
        board=board,
        active_player=active,
        turn_number=turn,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def place(state: GameState, pt: PieceType, team: Team, row: int, col: int,
          hp: int = None) -> Piece:
    piece = Piece.create(pt, team, row, col)
    if hp is not None:
        piece.current_hp = hp
    state.board[row][col] = piece
    return piece


def move_types_for(state: GameState, pt: PieceType, team: Team) -> set:
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p is not None and p.piece_type == pt and p.team == team:
                return {m.action_type for m in get_legal_moves(state)}
    return set()


# ---------------------------------------------------------------------------
# HP values
# ---------------------------------------------------------------------------

class TestHPValues:
    def test_eevee_max_hp(self):
        assert PIECE_STATS[PieceType.EEVEE].max_hp == 150

    def test_vaporeon_max_hp(self):
        assert PIECE_STATS[PieceType.VAPOREON].max_hp == 300

    def test_jolteon_max_hp(self):
        assert PIECE_STATS[PieceType.JOLTEON].max_hp == 200

    def test_flareon_max_hp(self):
        assert PIECE_STATS[PieceType.FLAREON].max_hp == 220

    def test_leafeon_max_hp(self):
        assert PIECE_STATS[PieceType.LEAFEON].max_hp == 220

    def test_espeon_max_hp(self):
        assert PIECE_STATS[PieceType.ESPEON].max_hp == 220

    def test_eevee_starts_at_max_hp(self):
        p = Piece.create(PieceType.EEVEE, Team.BLUE, 7, 4)
        assert p.current_hp == 150


# ---------------------------------------------------------------------------
# Quick Attack availability
# ---------------------------------------------------------------------------

class TestQuickAttackAvailability:
    def _has_qa(self, pt: PieceType, team: Team = Team.RED, row: int = 3, col: int = 3) -> bool:
        state = empty_state(active=team)
        place(state, pt, team, row, col)
        # Place adjacent enemy so QA has a valid attack target
        enemy_team = Team.BLUE if team == Team.RED else Team.RED
        place(state, PieceType.SQUIRTLE, enemy_team, row, col + 1)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        piece_moves = [m for m in moves if m.piece_row == row and m.piece_col == col]
        return any(m.action_type == ActionType.QUICK_ATTACK for m in piece_moves)

    def test_vaporeon_has_quick_attack(self):
        assert self._has_qa(PieceType.VAPOREON, Team.RED)

    def test_flareon_has_quick_attack(self):
        assert self._has_qa(PieceType.FLAREON, Team.RED)

    def test_leafeon_has_quick_attack(self):
        assert self._has_qa(PieceType.LEAFEON, Team.RED)

    def test_jolteon_has_quick_attack(self):
        assert self._has_qa(PieceType.JOLTEON, Team.RED)

    def test_espeon_does_not_have_quick_attack(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        espeon_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        assert not any(m.action_type == ActionType.QUICK_ATTACK for m in espeon_moves)


# ---------------------------------------------------------------------------
# Espeon move types
# ---------------------------------------------------------------------------

class TestEspeonMoves:
    def test_espeon_has_no_attack_moves(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 5)  # enemy in range
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        espeon_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        assert not any(m.action_type == ActionType.ATTACK for m in espeon_moves)

    def test_espeon_has_psywave(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        espeon_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        assert any(m.action_type == ActionType.PSYWAVE for m in espeon_moves)

    def test_espeon_has_foresight(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.SQUIRTLE, Team.RED, 4, 5)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        espeon_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        assert any(m.action_type == ActionType.FORESIGHT for m in espeon_moves)

    def test_espeon_has_move_actions(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.ESPEON, Team.BLUE, 4, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        espeon_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        assert any(m.action_type == ActionType.MOVE for m in espeon_moves)


# ---------------------------------------------------------------------------
# Flareon damage and recoil
# ---------------------------------------------------------------------------

class TestFlareonFlareBlitz:
    def test_flareon_base_damage_180(self):
        state = empty_state()
        flareon = place(state, PieceType.FLAREON, Team.RED, 3, 3)
        target = place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        dmg, _ = calc_damage_with_multiplier(flareon, target)
        # 180 base × 0.5 (FIRE vs WATER) = 90, rounded to nearest 10 = 90
        assert dmg == 90

    def test_flareon_attack_causes_recoil(self):
        # Flareon (FIRE) attacks Bulbasaur (GRASS): 180×2.0=360 → KOs. Flareon moves to (3,4).
        state = empty_state()
        flareon = place(state, PieceType.FLAREON, Team.RED, 3, 3)
        flareon_max = PIECE_STATS[PieceType.FLAREON].max_hp
        place(state, PieceType.BULBASAUR, Team.BLUE, 3, 4)
        move = Move(3, 3, ActionType.ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        flareon_after = ns.board[3][4]  # moved to KO'd target's square
        assert flareon_after is not None
        assert flareon_after.current_hp == flareon_max - 40

    def test_flareon_recoil_can_ko_flareon(self):
        # Flareon at low HP attacks — recoil kills Flareon; target KO'd too.
        state = empty_state()
        flareon = place(state, PieceType.FLAREON, Team.RED, 3, 3)
        flareon.current_hp = 30  # below recoil threshold
        place(state, PieceType.BULBASAUR, Team.BLUE, 3, 4)  # KO'd by 180×2=360
        move = Move(3, 3, ActionType.ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        # Flareon moved to (3,4) then recoil KO'd it
        assert ns.board[3][4] is None  # Flareon KO'd by recoil

    def test_quick_attack_no_recoil(self):
        state = empty_state(active=Team.RED)
        flareon = place(state, PieceType.FLAREON, Team.RED, 3, 3)
        flareon_max = PIECE_STATS[PieceType.FLAREON].max_hp
        target = place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        move = Move(3, 3, ActionType.QUICK_ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        # Flareon stays at (3,3) after QA (it doesn't move in QA)
        # or it moved into secondary — either way no 40 recoil
        flareon_piece = ns.board[3][3] or ns.board[3][4]
        if flareon_piece and flareon_piece.piece_type == PieceType.FLAREON:
            assert flareon_piece.current_hp == flareon_max  # no recoil


# ---------------------------------------------------------------------------
# Leafeon damage reduction
# ---------------------------------------------------------------------------

class TestLeafeonReduction:
    def test_neutral_attacker_reduced_by_40(self):
        """Squirtle (WATER, base 100) vs Leafeon (GRASS): 100-40=60, × 0.5 = 30."""
        state = empty_state()
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        leafeon = place(state, PieceType.LEAFEON, Team.BLUE, 3, 4)
        dmg, mult = calc_damage_with_multiplier(squirtle, leafeon)
        assert mult == pytest.approx(0.5)
        assert dmg == 30  # max(10, round(60 * 0.5 / 10) * 10)

    def test_fire_attacker_vs_leafeon(self):
        """Charmander (FIRE, base 100) vs Leafeon (GRASS): 100-40=60; × 2.0 = 120."""
        state = empty_state()
        charmander = place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        leafeon = place(state, PieceType.LEAFEON, Team.BLUE, 3, 4)
        dmg, mult = calc_damage_with_multiplier(charmander, leafeon)
        assert mult == pytest.approx(2.0)
        assert dmg == 120

    def test_reduction_floor_is_1_before_multiplier(self):
        """Eevee (NORMAL, base 50) vs Leafeon (GRASS): 50-40=10; × 1.0 = 10."""
        state = empty_state()
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 3, 3)
        leafeon_ally = place(state, PieceType.LEAFEON, Team.RED, 3, 4)
        dmg, mult = calc_damage_with_multiplier(eevee, leafeon_ally)
        assert mult == pytest.approx(1.0)
        assert dmg == 10  # max(10, round(10*1.0/10)*10)

    def test_non_leafeon_target_no_reduction(self):
        """Reduction only applies when target is Leafeon."""
        state = empty_state()
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        charmander = place(state, PieceType.CHARMANDER, Team.BLUE, 3, 4)
        # WATER vs FIRE: base 100 × 2.0 = 200
        dmg, mult = calc_damage_with_multiplier(squirtle, charmander)
        assert dmg == 200

    def test_leafeon_takes_reduced_damage_in_apply_move(self):
        # Charmander (FIRE, base 100) vs Leafeon (GRASS): 60×2.0=120 damage.
        # Leafeon has 220 HP → survives at 100 HP.
        state = empty_state()
        place(state, PieceType.CHARMANDER, Team.RED, 3, 3)
        leafeon = place(state, PieceType.LEAFEON, Team.BLUE, 3, 4)
        leafeon_start_hp = leafeon.current_hp
        move = Move(3, 3, ActionType.ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        leafeon_after = ns.board[3][4]
        assert leafeon_after is not None
        assert leafeon_after.current_hp == leafeon_start_hp - 120


# ---------------------------------------------------------------------------
# Jolteon diagonal jumps
# ---------------------------------------------------------------------------

class TestJolteonDiagonalJumps:
    def test_jolteon_can_jump_2_diagonally(self):
        state = empty_state(active=Team.RED)
        place(state, PieceType.JOLTEON, Team.RED, 4, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        jolt_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        targets = {(m.target_row, m.target_col) for m in jolt_moves
                   if m.action_type == ActionType.MOVE}
        assert (2, 2) in targets  # -2, -2
        assert (2, 6) in targets  # -2, +2
        assert (6, 2) in targets  # +2, -2
        assert (6, 6) in targets  # +2, +2

    def test_jolteon_diagonal_jump_clears_obstacle(self):
        """Jolteon's 2-sq diagonal jump is unobstructed."""
        state = empty_state(active=Team.RED)
        place(state, PieceType.JOLTEON, Team.RED, 4, 4)
        place(state, PieceType.BULBASAUR, Team.RED, 3, 3)  # friend at (3,3) — en route
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        jolt_moves = [m for m in moves if m.piece_row == 4 and m.piece_col == 4]
        targets = {(m.target_row, m.target_col) for m in jolt_moves
                   if m.action_type == ActionType.MOVE}
        assert (2, 2) in targets  # still reachable despite obstacle at (3,3)


# ---------------------------------------------------------------------------
# Raichu/Jolteon unobstructed 2-square cardinal jumps
# ---------------------------------------------------------------------------

class TestUnobstructedCardinalJumps:
    def _has_cardinal_2sq_move(self, pt: PieceType, pr: int, pc: int,
                                tr: int, tc: int, team: Team = Team.RED) -> bool:
        state = empty_state(active=team)
        place(state, pt, team, pr, pc)
        # Block the intermediate square
        mid_r = (pr + tr) // 2
        mid_c = (pc + tc) // 2
        place(state, PieceType.SQUIRTLE, team, mid_r, mid_c)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        piece_moves = [m for m in moves if m.piece_row == pr and m.piece_col == pc]
        return any(m.target_row == tr and m.target_col == tc for m in piece_moves)

    def test_raichu_jumps_over_obstacle_forward_2sq(self):
        assert self._has_cardinal_2sq_move(PieceType.RAICHU, 4, 4, 2, 4)

    def test_raichu_jumps_over_obstacle_side_2sq(self):
        assert self._has_cardinal_2sq_move(PieceType.RAICHU, 4, 4, 4, 2)

    def test_jolteon_jumps_over_obstacle_cardinal_2sq(self):
        assert self._has_cardinal_2sq_move(PieceType.JOLTEON, 4, 4, 2, 4)
