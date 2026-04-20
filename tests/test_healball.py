"""
Tests for Healball rule changes (TallGrass Update, criteria §21-25).

Covers:
  - Full-HP Pokemon blocked from entering Healball (any direction)
  - Only injured Pokemon may enter
  - Forward Healball entry move generated for injured non-Pikachu Pokemon
  - Forward entry stores piece correctly (same as Safetyball collection)
  - Pikachu cannot use forward Healball entry
  - Master Healball: instant full-HP heal on entry, no auto-release
  - Basic Healball: partial heal per turn, auto-release when full
  - Master Healball stays stored after entry (player must RELEASE manually)
"""

from __future__ import annotations

import pytest
from engine.state import (
    GameState, Piece, PieceType, Team, PIECE_STATS,
)
from engine.moves import Move, ActionType, get_legal_moves
from engine.rules import apply_move


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


def move_to(pr: int, pc: int, tr: int, tc: int) -> Move:
    return Move(piece_row=pr, piece_col=pc, action_type=ActionType.MOVE,
                target_row=tr, target_col=tc)


# ---------------------------------------------------------------------------
# Full-HP blocked, injured allowed
# ---------------------------------------------------------------------------

class TestHealballEntryRestriction:
    def test_full_hp_blocked_from_safetyball_move(self):
        """A Safetyball cannot absorb a full-HP ally (move onto it is blocked)."""
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 2, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 1)
        # Squirtle at full HP — Safetyball should not offer a MOVE targeting it
        squirtle.current_hp = squirtle.max_hp
        moves = get_legal_moves(state)
        sb_moves = [m for m in moves if m.piece_row == 2 and m.piece_col == 3]
        targets_with_squirtle = [m for m in sb_moves
                                 if m.target_row == 2 and m.target_col == 1]
        assert not targets_with_squirtle

    def test_injured_absorbed_by_safetyball(self):
        """An injured ally can be absorbed by a Safetyball moving onto them."""
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 2, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 1)
        squirtle.current_hp = squirtle.max_hp - 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        sb_moves = [m for m in moves if m.piece_row == 2 and m.piece_col == 3]
        targets_with_squirtle = [m for m in sb_moves
                                 if m.target_row == 2 and m.target_col == 1]
        assert targets_with_squirtle


# ---------------------------------------------------------------------------
# Forward Healball entry (Pokemon moves into Healball ahead)
# ---------------------------------------------------------------------------

class TestForwardHealballEntry:
    def test_forward_entry_move_generated_for_injured_piece(self):
        """An injured piece ahead of a friendly Healball should have a forward MOVE to it."""
        state = empty_state(active=Team.RED)
        # RED advances toward row 7 (fwd = +1 for RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 3, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 3)
        squirtle.current_hp = squirtle.max_hp - 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        sq_moves = [m for m in moves if m.piece_row == 2 and m.piece_col == 3]
        forward_entries = [m for m in sq_moves
                           if m.action_type == ActionType.MOVE
                           and m.target_row == 3 and m.target_col == 3]
        assert forward_entries

    def test_forward_entry_not_generated_for_full_hp_piece(self):
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 3, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 3)
        squirtle.current_hp = squirtle.max_hp  # full HP
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        sq_moves = [m for m in moves if m.piece_row == 2 and m.piece_col == 3]
        forward_entries = [m for m in sq_moves
                           if m.action_type == ActionType.MOVE
                           and m.target_row == 3 and m.target_col == 3]
        assert not forward_entries

    def test_pikachu_cannot_use_forward_entry(self):
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 1, 4)
        pika = place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        pika.current_hp = pika.max_hp - 10
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        pika_moves = [m for m in moves if m.piece_row == 0 and m.piece_col == 4]
        forward_entries = [m for m in pika_moves
                           if m.action_type == ActionType.MOVE
                           and m.target_row == 1 and m.target_col == 4]
        assert not forward_entries

    def test_forward_entry_stores_piece_in_healball(self):
        """When a piece moves forward into a Healball, it is stored inside."""
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 3, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 3)
        # Use very low HP so basic Safetyball heal (¼ max) doesn't trigger auto-release
        squirtle.current_hp = 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        move = move_to(2, 3, 3, 3)
        [(ns, _)] = apply_move(state, move)
        healball = ns.board[3][3]
        assert healball is not None
        assert healball.piece_type == PieceType.SAFETYBALL
        assert healball.stored_piece is not None
        assert healball.stored_piece.piece_type == PieceType.SQUIRTLE

    def test_forward_entry_removes_piece_from_original_square(self):
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 3, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 3)
        squirtle.current_hp = squirtle.max_hp - 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        move = move_to(2, 3, 3, 3)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[2][3] is None


# ---------------------------------------------------------------------------
# Master Healball: instant full heal, no auto-release
# ---------------------------------------------------------------------------

class TestMasterHealball:
    def test_master_healball_heals_to_full_on_entry(self):
        """Pokemon stored in Master Healball immediately heals to max HP."""
        state = empty_state(active=Team.RED)
        msb = place(state, PieceType.MASTER_SAFETYBALL, Team.RED, 2, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 1)
        squirtle.current_hp = 10  # very low HP
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        # Master Safetyball moves to absorb Squirtle
        move = move_to(2, 3, 2, 1)
        [(ns, _)] = apply_move(state, move)
        msb_after = ns.board[2][1]
        assert msb_after is not None
        assert msb_after.piece_type == PieceType.MASTER_SAFETYBALL
        assert msb_after.stored_piece is not None
        assert msb_after.stored_piece.current_hp == PIECE_STATS[PieceType.SQUIRTLE].max_hp

    def test_master_healball_holds_stored_piece_on_entry_turn(self):
        """Pokemon stays stored after the entry move (released on the NEXT turn)."""
        state = empty_state(active=Team.RED)
        msb = place(state, PieceType.MASTER_SAFETYBALL, Team.RED, 2, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 1)
        squirtle.current_hp = 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        move = move_to(2, 3, 2, 1)
        [(ns, _)] = apply_move(state, move)
        msb_after = ns.board[2][1]
        # Still stored after entry (release happens next turn)
        assert msb_after.stored_piece is not None

    def test_master_healball_auto_releases_on_next_move(self):
        """Master Safetyball auto-releases stored Pokemon when it moves again next turn."""
        state = empty_state(active=Team.RED)
        msb = place(state, PieceType.MASTER_SAFETYBALL, Team.RED, 2, 3)
        squirtle_stored = Piece.create(PieceType.SQUIRTLE, Team.RED, 2, 3)
        squirtle_stored.current_hp = PIECE_STATS[PieceType.SQUIRTLE].max_hp  # already full
        msb.stored_piece = squirtle_stored
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        # Move the Master Safetyball — stored piece is already full → auto-release
        move = move_to(2, 3, 2, 4)
        [(ns, _)] = apply_move(state, move)
        released = ns.board[2][4]
        assert released is not None
        assert released.piece_type == PieceType.SQUIRTLE
        assert released.current_hp == PIECE_STATS[PieceType.SQUIRTLE].max_hp

    def test_master_healball_piece_can_be_manually_released(self):
        """Stored Pokemon can be RELEASEd from Master Healball."""
        state = empty_state(active=Team.RED)
        msb = place(state, PieceType.MASTER_SAFETYBALL, Team.RED, 2, 3)
        squirtle_stored = Piece.create(PieceType.SQUIRTLE, Team.RED, 2, 3)
        squirtle_stored.current_hp = PIECE_STATS[PieceType.SQUIRTLE].max_hp
        msb.stored_piece = squirtle_stored
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        moves = get_legal_moves(state)
        release_moves = [m for m in moves
                         if m.piece_row == 2 and m.piece_col == 3
                         and m.action_type == ActionType.RELEASE]
        assert release_moves


# ---------------------------------------------------------------------------
# Basic Healball: partial heal, auto-release when full
# ---------------------------------------------------------------------------

class TestBasicHealball:
    def test_basic_healball_heals_quarter_per_turn(self):
        """Basic Healball heals ¼ max HP on each turn it is moved."""
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 2, 3)
        squirtle = place(state, PieceType.SQUIRTLE, Team.RED, 2, 1)
        mhp = PIECE_STATS[PieceType.SQUIRTLE].max_hp
        squirtle.current_hp = 10
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        # Absorb first
        move = move_to(2, 3, 2, 1)
        [(ns, _)] = apply_move(state, move)
        stored_hp_after_entry = ns.board[2][1].stored_piece.current_hp
        expected = min(10 + mhp // 4, mhp)
        assert stored_hp_after_entry == expected

    def test_basic_healball_auto_releases_when_full(self):
        """Basic Healball auto-releases stored piece when its HP reaches max."""
        state = empty_state(active=Team.RED)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, 2, 3)
        # Set stored piece at just-below-full so healing completes
        squirtle_stored = Piece.create(PieceType.SQUIRTLE, Team.RED, 2, 3)
        mhp = PIECE_STATS[PieceType.SQUIRTLE].max_hp
        squirtle_stored.current_hp = mhp - 1  # one tick away from full
        sb.stored_piece = squirtle_stored
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        # Move the Safetyball one step; healing fires
        move = move_to(2, 3, 2, 4)
        [(ns, _)] = apply_move(state, move)
        # Stored piece should be placed on the board (auto-released)
        sq_released = ns.board[2][4]
        assert sq_released is not None
        assert sq_released.piece_type == PieceType.SQUIRTLE
        assert sq_released.current_hp == mhp
