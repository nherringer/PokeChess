"""
Tests for variable Pokeball catch rates (TallGrass Update, criteria §14-16).

Non-Mew catch rates (HP-based bins):
  - full HP (ratio == 1.0)    → 25% catch, 75% fail
  - mid HP  (0.5 ≤ ratio < 1) → 50% catch, 50% fail
  - low HP  (ratio < 0.5)     → 75% catch, 25% fail

Mew catch rates:
  - full HP  → 20% catch, 80% fail
  - mid HP   → 40% catch, 60% fail
  - low HP   → 60% catch, 40% fail

Masterball: guaranteed capture (single deterministic outcome).
"""

from __future__ import annotations

import pytest
from engine.state import GameState, Piece, PieceType, Team, Item, PIECE_STATS
from engine.moves import Move, ActionType
from engine.rules import apply_move


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def empty_state(active: Team = Team.RED) -> GameState:
    board = [[None] * 8 for _ in range(8)]
    return GameState(
        board=board,
        active_player=active,
        turn_number=1,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def place(state: GameState, pt: PieceType, team: Team, row: int, col: int,
          hp: int = None) -> Piece:
    piece = Piece.create(pt, team, row, col)
    if hp is not None:
        piece.current_hp = hp
    state.board[row][col] = piece
    return piece


def pokeball_attack(pr: int, pc: int, tr: int, tc: int) -> Move:
    return Move(piece_row=pr, piece_col=pc, action_type=ActionType.ATTACK,
                target_row=tr, target_col=tc)


def catch_prob(results) -> float:
    """Return the capture outcome probability from a stochastic result list."""
    capture = next(
        (p for s, p in results if s.board[3][3] is None and s.board[3][4] is None),
        None
    )
    assert capture is not None, "No capture outcome found"
    return capture


# ---------------------------------------------------------------------------
# Non-Mew: Squirtle (representative non-Mew, WATER type)
# ---------------------------------------------------------------------------

class TestNonMewCatchRates:
    PIECE = PieceType.SQUIRTLE

    def _max_hp(self):
        return PIECE_STATS[self.PIECE].max_hp

    def _run(self, hp: int):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, self.PIECE, Team.BLUE, 3, 4, hp=hp)
        return apply_move(state, pokeball_attack(3, 3, 3, 4))

    def test_full_hp_catch_rate_is_25pct(self):
        results = self._run(self._max_hp())
        probs = sorted(p for _, p in results)
        assert probs == pytest.approx([0.25, 0.75])

    def test_mid_hp_catch_rate_is_50pct(self):
        mhp = self._max_hp()
        mid_hp = int(mhp * 0.75)  # 75% HP → in the mid bin (0.5 ≤ ratio < 1)
        results = self._run(mid_hp)
        probs = sorted(p for _, p in results)
        assert probs == pytest.approx([0.50, 0.50])

    def test_low_hp_catch_rate_is_75pct(self):
        mhp = self._max_hp()
        low_hp = max(1, int(mhp * 0.3))  # 30% HP → low bin (ratio < 0.5)
        results = self._run(low_hp)
        probs = sorted(p for _, p in results)
        assert probs == pytest.approx([0.25, 0.75])  # 75% catch = [0.25 fail, 0.75 catch]

    def test_low_hp_is_75pct_catch(self):
        mhp = self._max_hp()
        low_hp = max(1, int(mhp * 0.3))
        results = self._run(low_hp)
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.75)

    def test_full_hp_is_25pct_catch(self):
        results = self._run(self._max_hp())
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.25)

    def test_mid_hp_boundary_exactly_half(self):
        """HP exactly at 50% of max is in mid bin (0.5 ≤ ratio < 1.0)."""
        mhp = self._max_hp()
        half_hp = mhp // 2
        results = self._run(half_hp)
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.50)

    def test_probabilities_sum_to_one_all_bins(self):
        mhp = self._max_hp()
        for hp in [mhp, mhp * 3 // 4, mhp // 2, max(1, mhp // 4)]:
            results = self._run(hp)
            total = sum(p for _, p in results)
            assert total == pytest.approx(1.0)

    def test_raichu_full_hp_25pct(self):
        """Raichu (post-evolution, not Pikachu) has standard non-Mew catch rate."""
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.RAICHU, Team.BLUE, 3, 4, hp=PIECE_STATS[PieceType.RAICHU].max_hp)
        results = apply_move(state, pokeball_attack(3, 3, 3, 4))
        probs = sorted(p for _, p in results)
        assert probs == pytest.approx([0.25, 0.75])


# ---------------------------------------------------------------------------
# Mew catch rates
# ---------------------------------------------------------------------------

class TestMewCatchRates:
    PIECE = PieceType.MEW

    def _max_hp(self):
        return PIECE_STATS[self.PIECE].max_hp

    def _run(self, hp: int):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, self.PIECE, Team.BLUE, 3, 4, hp=hp)
        return apply_move(state, pokeball_attack(3, 3, 3, 4))

    def test_full_hp_catch_rate_is_20pct(self):
        results = self._run(self._max_hp())
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.20)

    def test_mid_hp_catch_rate_is_40pct(self):
        mhp = self._max_hp()
        mid_hp = int(mhp * 0.75)
        results = self._run(mid_hp)
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.40)

    def test_low_hp_catch_rate_is_60pct(self):
        mhp = self._max_hp()
        low_hp = max(1, int(mhp * 0.3))
        results = self._run(low_hp)
        p_catch = catch_prob(results)
        assert p_catch == pytest.approx(0.60)

    def test_mew_full_hp_different_from_non_mew(self):
        mhp = self._max_hp()
        results = self._run(mhp)
        p_catch_mew = catch_prob(results)
        # Non-Mew full HP is 0.25; Mew is 0.20
        assert p_catch_mew == pytest.approx(0.20)
        assert p_catch_mew != pytest.approx(0.25)

    def test_probabilities_sum_to_one(self):
        mhp = self._max_hp()
        for hp in [mhp, mhp * 3 // 4, max(1, mhp // 4)]:
            results = self._run(hp)
            assert sum(p for _, p in results) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Pikachu immunity (unchanged)
# ---------------------------------------------------------------------------

class TestPikachuImmunity:
    def test_pikachu_immune_to_pokeball(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        results = apply_move(state, pokeball_attack(3, 3, 3, 4))
        assert len(results) == 1
        ns, p = results[0]
        assert p == pytest.approx(1.0)
        assert ns.board[3][4] is not None  # Pikachu survives


# ---------------------------------------------------------------------------
# Masterball: guaranteed capture
# ---------------------------------------------------------------------------

class TestMasterball:
    def test_masterball_always_captures(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        results = apply_move(state, pokeball_attack(3, 3, 3, 4))
        assert len(results) == 1
        ns, p = results[0]
        assert p == pytest.approx(1.0)
        assert ns.board[3][3] is None
        assert ns.board[3][4] is None

    def test_masterball_captures_mew(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.MEW, Team.BLUE, 3, 4)
        results = apply_move(state, pokeball_attack(3, 3, 3, 4))
        assert len(results) == 1
        _, p = results[0]
        assert p == pytest.approx(1.0)

    def test_masterball_bypasses_pikachu_immunity(self):
        """Masterball is the only ball that can capture Pikachu."""
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.PIKACHU, Team.BLUE, 3, 4)
        results = apply_move(state, pokeball_attack(3, 3, 3, 4))
        assert len(results) == 1
        ns, p = results[0]
        assert p == pytest.approx(1.0)
        assert ns.board[3][3] is None and ns.board[3][4] is None
