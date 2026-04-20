"""
Tests for item drops from KOs and Foresight, and serialization round-trip.

Covers Task #24:
  - Standard KO attack: attacker auto-picks up if empty-handed
  - Standard KO attack: overflow when attacker already holds item
  - Pokeball capture (capture_both): item dropped on capture square
  - Foresight KO: item dropped on vacated square as floor item
  - Quick Attack KO: item transferred same as regular attack KO
  - Psywave KO: item dropped on vacated square as floor item
  - Serialization: state_to_dict / state_from_dict round-trips hidden_items,
    floor_items, and tall_grass_explored cleanly
"""

from __future__ import annotations

import pytest
from engine.state import (
    GameState, Piece, PieceType, Team, Item, HiddenItem, FloorItem,
    TALL_GRASS_ROWS, PIECE_STATS, ForesightEffect,
)
from engine.moves import Move, ActionType
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
          item: Item = Item.NONE, hp: int = None) -> Piece:
    piece = Piece.create(pt, team, row, col)
    piece.held_item = item
    if hp is not None:
        piece.current_hp = hp
    state.board[row][col] = piece
    return piece


def make_move(pr: int, pc: int, at: ActionType, tr: int, tc: int, **kw) -> Move:
    return Move(piece_row=pr, piece_col=pc, action_type=at,
                target_row=tr, target_col=tc, **kw)


def one_shot_hp(attacker_type: PieceType) -> int:
    """Return 1 HP to ensure any attack KOs the target."""
    return 1


# ---------------------------------------------------------------------------
# Standard attack KO item transfer
# ---------------------------------------------------------------------------

class TestAttackKOItemTransfer:
    def test_attacker_picks_up_item_on_ko(self):
        """Empty-handed attacker auto-picks up target's item after KO."""
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 5, item=Item.FIRESTONE, hp=1)
        move = make_move(3, 3, ActionType.ATTACK, 3, 5)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[3][5].held_item == Item.FIRESTONE  # attacker moved there
        assert ns.floor_items == []

    def test_attacker_overflow_on_ko(self):
        """Attacker holding item triggers overflow when target also holds one after KO."""
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3, item=Item.WATERSTONE)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 5, item=Item.FIRESTONE, hp=1)
        move = make_move(3, 3, ActionType.ATTACK, 3, 5,
                         overflow_keep='existing', overflow_drop_row=3, overflow_drop_col=4)
        [(ns, _)] = apply_move(state, move)
        attacker = ns.board[3][5]
        assert attacker.held_item == Item.WATERSTONE
        dropped = [fi for fi in ns.floor_items if fi.item == Item.FIRESTONE]
        assert len(dropped) == 1

    def test_no_floor_item_when_target_holds_none(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 3)
        place(state, PieceType.CHARMANDER, Team.BLUE, 3, 5, hp=1)
        move = make_move(3, 3, ActionType.ATTACK, 3, 5)
        [(ns, _)] = apply_move(state, move)
        assert ns.floor_items == []


# ---------------------------------------------------------------------------
# Masterball capture drops target's item
# ---------------------------------------------------------------------------

class TestMasterballCaptureDrop:
    def test_masterball_drops_target_item(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4, item=Item.WATERSTONE)
        move = make_move(3, 3, ActionType.ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        floor = [fi for fi in ns.floor_items if fi.item == Item.WATERSTONE]
        assert len(floor) == 1
        assert floor[0].row == 3 and floor[0].col == 4

    def test_masterball_no_floor_item_when_target_empty(self):
        state = empty_state()
        place(state, PieceType.MASTERBALL, Team.RED, 3, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4)
        move = make_move(3, 3, ActionType.ATTACK, 3, 4)
        [(ns, _)] = apply_move(state, move)
        assert ns.floor_items == []


# ---------------------------------------------------------------------------
# Foresight KO item drop
# ---------------------------------------------------------------------------

class TestForesightKODrop:
    def test_foresight_ko_drops_item_on_vacated_square(self):
        """When Foresight kills a piece holding an item, the item drops as a floor item."""
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 0, 3)
        target = place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 3, item=Item.WATERSTONE, hp=1)
        # Queue a foresight that resolves this turn with lethal damage
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=3, target_col=3,
            damage=500,
            resolves_on_turn=3,
            caster_row=0, caster_col=3,
        )
        # Any move to trigger turn resolution; use Mew MOVE
        move = make_move(0, 3, ActionType.MOVE, 0, 2)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[3][3] is None
        floor = [fi for fi in ns.floor_items if fi.item == Item.WATERSTONE]
        assert len(floor) == 1
        assert floor[0].row == 3 and floor[0].col == 3

    def test_foresight_no_drop_when_target_empty(self):
        state = empty_state(active=Team.RED, turn=3)
        place(state, PieceType.MEW, Team.RED, 0, 3)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 3, hp=1)
        state.pending_foresight[Team.RED] = ForesightEffect(
            target_row=3, target_col=3,
            damage=500,
            resolves_on_turn=3,
            caster_row=0, caster_col=3,
        )
        move = make_move(0, 3, ActionType.MOVE, 0, 2)
        [(ns, _)] = apply_move(state, move)
        assert ns.floor_items == []


# ---------------------------------------------------------------------------
# Quick Attack KO item transfer
# ---------------------------------------------------------------------------

class TestQuickAttackKOItemTransfer:
    def test_quick_attack_ko_transfers_item(self):
        """Eevee Quick Attack that KOs a piece transfers the item to Eevee."""
        state = empty_state(active=Team.BLUE)
        eevee = place(state, PieceType.EEVEE, Team.BLUE, 6, 3)
        place(state, PieceType.SQUIRTLE, Team.RED, 5, 3, item=Item.WATERSTONE, hp=1)
        move = make_move(6, 3, ActionType.QUICK_ATTACK, 5, 3)
        [(ns, _)] = apply_move(state, move)
        eevee_after = ns.board[5][3]
        if eevee_after is not None:
            assert eevee_after.held_item == Item.WATERSTONE
        else:
            assert any(fi.item == Item.WATERSTONE for fi in ns.floor_items)


# ---------------------------------------------------------------------------
# Psywave KO item drop
# ---------------------------------------------------------------------------

class TestPsywaveKODrop:
    def test_psywave_ko_drops_item(self):
        """Psywave KO of an item-holding piece drops a floor item at the vacated square."""
        state = empty_state(active=Team.BLUE)
        espeon = place(state, PieceType.ESPEON, Team.BLUE, 7, 3)
        target = place(state, PieceType.SQUIRTLE, Team.RED, 6, 3, item=Item.WATERSTONE, hp=1)
        move = make_move(7, 3, ActionType.PSYWAVE, 7, 3)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[6][3] is None
        floor = [fi for fi in ns.floor_items if fi.item == Item.WATERSTONE]
        assert len(floor) == 1


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------

class TestSerializationRoundTrip:
    def test_hidden_items_round_trip(self):
        from app.game_logic.serialization import state_to_dict, state_from_dict
        state = empty_state()
        state.hidden_items = [
            HiddenItem(row=2, col=3, item=Item.WATERSTONE),
            HiddenItem(row=4, col=5, item=Item.THUNDERSTONE),
        ]
        d = state_to_dict(state, {})
        state2, _ = state_from_dict(d)
        items = {(h.row, h.col, h.item) for h in state2.hidden_items}
        assert items == {(2, 3, Item.WATERSTONE), (4, 5, Item.THUNDERSTONE)}

    def test_floor_items_round_trip(self):
        from app.game_logic.serialization import state_to_dict, state_from_dict
        state = empty_state()
        state.floor_items = [FloorItem(row=3, col=4, item=Item.FIRESTONE)]
        d = state_to_dict(state, {})
        state2, _ = state_from_dict(d)
        assert len(state2.floor_items) == 1
        fi = state2.floor_items[0]
        assert fi.row == 3 and fi.col == 4 and fi.item == Item.FIRESTONE

    def test_tall_grass_explored_round_trip(self):
        from app.game_logic.serialization import state_to_dict, state_from_dict
        state = empty_state()
        state.tall_grass_explored = {(2, 3), (4, 7)}
        d = state_to_dict(state, {})
        state2, _ = state_from_dict(d)
        assert state2.tall_grass_explored == {(2, 3), (4, 7)}

    def test_empty_fields_round_trip(self):
        from app.game_logic.serialization import state_to_dict, state_from_dict
        state = empty_state()
        d = state_to_dict(state, {})
        state2, _ = state_from_dict(d)
        assert state2.hidden_items == []
        assert state2.floor_items == []
        assert state2.tall_grass_explored == set()

    def test_full_new_game_round_trip(self):
        from app.game_logic.serialization import state_to_dict, state_from_dict
        state = GameState.new_game()
        d = state_to_dict(state, {})
        state2, _ = state_from_dict(d)
        assert len(state2.hidden_items) == 4
        assert state2.floor_items == []
        assert state2.tall_grass_explored == set()
