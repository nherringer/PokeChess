"""
Tests for engine-side serialization:
  - GameState.from_dict()  (engine/state.py)
  - Move.to_dict()         (engine/moves.py)
"""
from __future__ import annotations

import pytest

from engine.state import (
    GameState,
    Piece,
    ForesightEffect,
    PieceType,
    Team,
    Item,
)
from engine.moves import ActionType, Move


# ---------------------------------------------------------------------------
# Helpers — build test fixtures without touching app/
# ---------------------------------------------------------------------------

def _make_board() -> list[list]:
    return [[None] * 8 for _ in range(8)]


def _piece_dict(
    piece_type: str,
    team: str,
    row: int,
    col: int,
    current_hp: int,
    held_item: str = "NONE",
    stored_piece: dict | None = None,
    id: str | None = None,
) -> dict:
    return {
        "id": id,
        "piece_type": piece_type,
        "team": team,
        "row": row,
        "col": col,
        "current_hp": current_hp,
        "held_item": held_item,
        "stored_piece": stored_piece,
    }


def _foresight_dict(target_row: int, target_col: int, damage: int, resolves_on_turn: int) -> dict:
    return {
        "target_row": target_row,
        "target_col": target_col,
        "damage": damage,
        "resolves_on_turn": resolves_on_turn,
    }


def _minimal_state_dict(board_pieces: list[dict], **overrides) -> dict:
    """Build a complete wire-format state dict with sensible defaults."""
    base = {
        "active_player": "RED",
        "turn_number": 1,
        "has_traded": {"RED": False, "BLUE": False},
        "foresight_used_last_turn": {"RED": False, "BLUE": False},
        "pending_foresight": {"RED": None, "BLUE": None},
        "board": board_pieces,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# FEN round-trip tests
# ---------------------------------------------------------------------------

class TestFenRoundTrip:
    """
    Build a mid-game dict (as the app would produce), deserialize via
    GameState.from_dict(), and assert all fields match expectations.
    """

    def test_basic_positions_and_hp(self):
        """Pieces end up at the correct board positions with correct HP."""
        pieces = [
            _piece_dict("PIKACHU",    "RED",  0, 4, 200, "THUNDERSTONE"),
            _piece_dict("SQUIRTLE",   "RED",  3, 2, 150, "WATERSTONE"),
            _piece_dict("EEVEE",      "BLUE", 7, 4, 120, "NONE"),
            _piece_dict("CHARMANDER", "BLUE", 5, 1, 180, "FIRESTONE"),
        ]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)

        pika = state.board[0][4]
        assert pika is not None
        assert pika.piece_type == PieceType.PIKACHU
        assert pika.team == Team.RED
        assert pika.current_hp == 200
        assert pika.held_item == Item.THUNDERSTONE

        squi = state.board[3][2]
        assert squi is not None
        assert squi.piece_type == PieceType.SQUIRTLE
        assert squi.current_hp == 150

        eevee = state.board[7][4]
        assert eevee is not None
        assert eevee.piece_type == PieceType.EEVEE
        assert eevee.team == Team.BLUE

        charm = state.board[5][1]
        assert charm is not None
        assert charm.piece_type == PieceType.CHARMANDER
        assert charm.held_item == Item.FIRESTONE

    def test_active_player_and_turn(self):
        pieces = [_piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(pieces, active_player="BLUE", turn_number=12)
        state = GameState.from_dict(d)
        assert state.active_player == Team.BLUE
        assert state.turn_number == 12

    def test_has_traded_flags(self):
        pieces = [_piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(pieces, has_traded={"RED": True, "BLUE": False})
        state = GameState.from_dict(d)
        assert state.has_traded[Team.RED] is True
        assert state.has_traded[Team.BLUE] is False

    def test_foresight_used_last_turn_flags(self):
        pieces = [_piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(
            pieces,
            foresight_used_last_turn={"RED": False, "BLUE": True},
        )
        state = GameState.from_dict(d)
        assert state.foresight_used_last_turn[Team.RED] is False
        assert state.foresight_used_last_turn[Team.BLUE] is True

    def test_pending_foresight_none(self):
        pieces = [_piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)
        assert state.pending_foresight[Team.RED] is None
        assert state.pending_foresight[Team.BLUE] is None

    def test_pending_foresight_both_set(self):
        pieces = [_piece_dict("MEW", "RED", 0, 3, 250), _piece_dict("ESPEON", "BLUE", 7, 3, 220)]
        fx_red = _foresight_dict(4, 4, 100, 5)
        fx_blue = _foresight_dict(3, 3, 80, 6)
        d = _minimal_state_dict(
            pieces,
            pending_foresight={"RED": fx_red, "BLUE": fx_blue},
            foresight_used_last_turn={"RED": True, "BLUE": True},
        )
        state = GameState.from_dict(d)

        red_fx = state.pending_foresight[Team.RED]
        assert isinstance(red_fx, ForesightEffect)
        assert red_fx.target_row == 4
        assert red_fx.target_col == 4
        assert red_fx.damage == 100
        assert red_fx.resolves_on_turn == 5

        blue_fx = state.pending_foresight[Team.BLUE]
        assert isinstance(blue_fx, ForesightEffect)
        assert blue_fx.target_row == 3
        assert blue_fx.target_col == 3
        assert blue_fx.damage == 80
        assert blue_fx.resolves_on_turn == 6

    def test_pending_foresight_with_caster_fields(self):
        """Foresight dict that includes caster_row/caster_col deserializes them correctly."""
        pieces = [_piece_dict("MEW", "RED", 0, 3, 250), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        fx = {
            "target_row": 4,
            "target_col": 4,
            "damage": 120,
            "resolves_on_turn": 7,
            "caster_row": 0,
            "caster_col": 3,
        }
        d = _minimal_state_dict(
            pieces,
            pending_foresight={"RED": fx, "BLUE": None},
            foresight_used_last_turn={"RED": True, "BLUE": False},
        )
        state = GameState.from_dict(d)

        red_fx = state.pending_foresight[Team.RED]
        assert isinstance(red_fx, ForesightEffect)
        assert red_fx.caster_row == 0
        assert red_fx.caster_col == 3
        assert red_fx.target_row == 4
        assert red_fx.target_col == 4
        assert red_fx.damage == 120
        assert red_fx.resolves_on_turn == 7

    def test_pending_foresight_without_caster_fields_defaults_to_minus_one(self):
        """Old-format foresight dict (no caster_row/col) defaults to -1 for compat."""
        pieces = [_piece_dict("MEW", "RED", 0, 3, 250), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        fx = _foresight_dict(4, 4, 120, 7)  # no caster fields
        d = _minimal_state_dict(
            pieces,
            pending_foresight={"RED": fx, "BLUE": None},
        )
        state = GameState.from_dict(d)

        red_fx = state.pending_foresight[Team.RED]
        assert isinstance(red_fx, ForesightEffect)
        assert red_fx.caster_row == -1
        assert red_fx.caster_col == -1

    def test_stored_piece_in_safetyball(self):
        """Safetyball with a stored piece deserializes the nested piece correctly."""
        stored = _piece_dict("BULBASAUR", "RED", 2, 3, 80, "LEAFSTONE")
        safetyball = _piece_dict("SAFETYBALL", "RED", 2, 3, 0, "NONE", stored_piece=stored)
        pieces = [safetyball, _piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)

        sb = state.board[2][3]
        assert sb is not None
        assert sb.piece_type == PieceType.SAFETYBALL
        assert sb.stored_piece is not None
        inner = sb.stored_piece
        assert inner.piece_type == PieceType.BULBASAUR
        assert inner.team == Team.RED
        assert inner.current_hp == 80
        assert inner.held_item == Item.LEAFSTONE

    def test_all_items_round_trip(self):
        """Every Item value can be deserialized."""
        for item in Item:
            pieces = [
                _piece_dict("SQUIRTLE", "RED", 0, 0, 200, item.name),
                _piece_dict("PIKACHU", "RED", 0, 4, 200),
                _piece_dict("EEVEE", "BLUE", 7, 4, 120),
            ]
            d = _minimal_state_dict(pieces)
            state = GameState.from_dict(d)
            assert state.board[0][0].held_item == item

    def test_full_round_trip_hand_built_dict(self):
        """
        Hand-build a wire-format dict matching what app's state_to_dict() would produce,
        deserialize with GameState.from_dict(), and check every field matches.
        """
        stored_piece_dict = _piece_dict("BULBASAUR", "RED", 2, 2, 80, "LEAFSTONE", id="bulb-uuid")
        pieces = [
            _piece_dict("PIKACHU", "RED", 0, 4, 200, "THUNDERSTONE"),
            _piece_dict("SQUIRTLE", "RED", 3, 0, 150, "WATERSTONE"),
            _piece_dict("SAFETYBALL", "RED", 2, 2, 0, "NONE", stored_piece=stored_piece_dict),
            _piece_dict("EEVEE", "BLUE", 7, 4, 120, "NONE"),
            _piece_dict("MEW", "BLUE", 6, 3, 250, "BENTSPOON"),
        ]
        foresight_red = _foresight_dict(4, 4, 100, 8)
        d = _minimal_state_dict(
            pieces,
            active_player="BLUE",
            turn_number=7,
            pending_foresight={"RED": foresight_red, "BLUE": None},
            foresight_used_last_turn={"RED": True, "BLUE": False},
            has_traded={"RED": False, "BLUE": True},
        )

        state = GameState.from_dict(d)

        assert state.active_player == Team.BLUE
        assert state.turn_number == 7
        assert state.has_traded == {Team.RED: False, Team.BLUE: True}
        assert state.foresight_used_last_turn == {Team.RED: True, Team.BLUE: False}

        rfx = state.pending_foresight[Team.RED]
        assert rfx is not None
        assert rfx.target_row == 4
        assert rfx.target_col == 4
        assert rfx.damage == 100
        assert rfx.resolves_on_turn == 8
        assert state.pending_foresight[Team.BLUE] is None

        pika = state.board[0][4]
        assert pika.piece_type == PieceType.PIKACHU
        assert pika.team == Team.RED
        assert pika.current_hp == 200

        squi = state.board[3][0]
        assert squi.piece_type == PieceType.SQUIRTLE
        assert squi.current_hp == 150

        eevee = state.board[7][4]
        assert eevee.piece_type == PieceType.EEVEE

        mew = state.board[6][3]
        assert mew.piece_type == PieceType.MEW
        assert mew.held_item == Item.BENTSPOON

        rsb = state.board[2][2]
        assert rsb.piece_type == PieceType.SAFETYBALL
        assert rsb.stored_piece is not None
        assert rsb.stored_piece.piece_type == PieceType.BULBASAUR
        assert rsb.stored_piece.current_hp == 80
        assert rsb.stored_piece.id == "bulb-uuid"

        assert state.board[4][4] is None


# ---------------------------------------------------------------------------
# UUID passthrough tests
# ---------------------------------------------------------------------------

class TestUuidPassthrough:
    def test_piece_with_id_field_deserializes_without_error(self):
        """Piece dicts with an 'id' key must not cause errors."""
        pieces = [
            _piece_dict("PIKACHU", "RED", 0, 4, 200, "THUNDERSTONE", id="uuid-pikachu-001"),
            _piece_dict("EEVEE", "BLUE", 7, 4, 120, "NONE", id="uuid-eevee-002"),
        ]
        d = _minimal_state_dict(pieces)
        # Must not raise
        state = GameState.from_dict(d)
        assert state.board[0][4].piece_type == PieceType.PIKACHU
        assert state.board[7][4].piece_type == PieceType.EEVEE

    def test_piece_id_is_preserved_on_piece(self):
        """The id field is carried through onto the Piece object."""
        pieces = [
            _piece_dict("PIKACHU", "RED", 0, 4, 200, "THUNDERSTONE", id="my-uuid"),
            _piece_dict("EEVEE", "BLUE", 7, 4, 120, "NONE"),
        ]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)
        assert state.board[0][4].id == "my-uuid"

    def test_piece_without_id_field_has_none(self):
        """Piece dicts without 'id' should result in Piece.id == None."""
        pieces = [
            # no id key at all
            {"piece_type": "PIKACHU", "team": "RED", "row": 0, "col": 4,
             "current_hp": 200, "held_item": "THUNDERSTONE", "stored_piece": None},
            _piece_dict("EEVEE", "BLUE", 7, 4, 120),
        ]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)
        assert state.board[0][4].id is None

    def test_stored_piece_id_preserved(self):
        """UUID on a stored piece is passed through."""
        stored = _piece_dict("BULBASAUR", "RED", 2, 3, 80, "LEAFSTONE", id="stored-uuid")
        safetyball = _piece_dict("SAFETYBALL", "RED", 2, 3, 0, "NONE", stored_piece=stored)
        pieces = [safetyball, _piece_dict("PIKACHU", "RED", 0, 4, 200), _piece_dict("EEVEE", "BLUE", 7, 4, 120)]
        d = _minimal_state_dict(pieces)
        state = GameState.from_dict(d)
        assert state.board[2][3].stored_piece.id == "stored-uuid"

    def test_round_trip_with_ids_hand_built_dict(self):
        """GameState with id-bearing pieces round-trips correctly without error."""
        pieces = [
            _piece_dict("PIKACHU", "RED", 0, 4, 200, "THUNDERSTONE", id="pika-uuid"),
            _piece_dict("EEVEE", "BLUE", 7, 4, 120, "NONE", id="eevee-uuid"),
        ]
        d = _minimal_state_dict(pieces)
        restored = GameState.from_dict(d)
        assert restored.board[0][4].id == "pika-uuid"
        assert restored.board[7][4].id == "eevee-uuid"


# ---------------------------------------------------------------------------
# Move.to_dict() tests
# ---------------------------------------------------------------------------

class TestMoveToDict:

    def test_move_action_type_is_string(self):
        m = Move(piece_row=1, piece_col=2, action_type=ActionType.MOVE, target_row=2, target_col=2)
        d = m.to_dict()
        assert d["action_type"] == "MOVE"
        assert isinstance(d["action_type"], str)

    def test_optional_fields_null_when_absent(self):
        m = Move(piece_row=0, piece_col=0, action_type=ActionType.ATTACK, target_row=1, target_col=1)
        d = m.to_dict()
        assert d["secondary_row"] is None
        assert d["secondary_col"] is None
        assert d["move_slot"] is None

    def test_move_slot_present_for_mew_attack(self):
        m = Move(piece_row=0, piece_col=3, action_type=ActionType.ATTACK, target_row=3, target_col=3, move_slot=2)
        d = m.to_dict()
        assert d["move_slot"] == 2

    def test_quick_attack_secondary_fields(self):
        m = Move(
            piece_row=7, piece_col=4,
            action_type=ActionType.QUICK_ATTACK,
            target_row=6, target_col=4,
            secondary_row=6, secondary_col=3,
        )
        d = m.to_dict()
        assert d["action_type"] == "QUICK_ATTACK"
        assert d["target_row"] == 6
        assert d["target_col"] == 4
        assert d["secondary_row"] == 6
        assert d["secondary_col"] == 3
        assert d["move_slot"] is None

    def test_quick_attack_with_no_secondary_is_null(self):
        """secondary_row/col remain null when not provided (shouldn't happen in legal moves, but API contract holds)."""
        m = Move(piece_row=7, piece_col=4, action_type=ActionType.QUICK_ATTACK, target_row=6, target_col=4)
        d = m.to_dict()
        assert d["secondary_row"] is None
        assert d["secondary_col"] is None

    @pytest.mark.parametrize("action_type", list(ActionType))
    def test_every_action_type_serializes(self, action_type: ActionType):
        """Every ActionType value can be serialized; action_type field is always the enum name."""
        m = Move(piece_row=0, piece_col=0, action_type=action_type, target_row=0, target_col=0)
        d = m.to_dict()
        assert d["action_type"] == action_type.name

    def test_scalar_fields_verbatim(self):
        m = Move(piece_row=3, piece_col=5, action_type=ActionType.FORESIGHT, target_row=6, target_col=2)
        d = m.to_dict()
        assert d["piece_row"] == 3
        assert d["piece_col"] == 5
        assert d["target_row"] == 6
        assert d["target_col"] == 2

    def test_evolve_move(self):
        m = Move(piece_row=7, piece_col=4, action_type=ActionType.EVOLVE, target_row=7, target_col=4, move_slot=0)
        d = m.to_dict()
        assert d["action_type"] == "EVOLVE"
        assert d["move_slot"] == 0
        assert d["secondary_row"] is None
        assert d["secondary_col"] is None

    def test_trade_move(self):
        m = Move(piece_row=0, piece_col=4, action_type=ActionType.TRADE, target_row=0, target_col=3)
        d = m.to_dict()
        assert d["action_type"] == "TRADE"
        assert d["move_slot"] is None
        assert d["secondary_row"] is None

    def test_release_move(self):
        m = Move(piece_row=2, piece_col=2, action_type=ActionType.RELEASE, target_row=2, target_col=2)
        d = m.to_dict()
        assert d["action_type"] == "RELEASE"
