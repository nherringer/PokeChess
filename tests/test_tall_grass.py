"""
Tests for tall grass item discovery mechanics (TallGrass Update).

Covers:
  - Item initialization: no starting items, 4 hidden items in TALL_GRASS_ROWS
  - Exploration: non-Pokeball moving to unexplored square reveals it
  - Auto-pickup: empty-handed piece picks up item automatically
  - Overflow with explicit keep/drop: keep existing vs keep new
  - Overflow default (bot path): keep existing, drop new row-major first open square
  - Pokeballs do not explore tall grass
  - Expelled/discharged Pokemon landing on unexplored squares explore them
  - Floor items visible in player_view_of_state
  - KO drops: Pokeball capture drops item on capture square
  - Foresight KO drops item on vacated square
  - player_view_of_state hides hidden_items, masks opponent held_item identity
"""

from __future__ import annotations

import pytest
from engine.state import (
    GameState, Piece, PieceType, Team, Item, HiddenItem, FloorItem,
    TALL_GRASS_ROWS, PIECE_STATS,
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
          item: Item = Item.NONE) -> Piece:
    piece = Piece.create(pt, team, row, col)
    piece.held_item = item
    state.board[row][col] = piece
    return piece


def make_move(pr: int, pc: int, at: ActionType, tr: int, tc: int, **kw) -> Move:
    return Move(piece_row=pr, piece_col=pc, action_type=at,
                target_row=tr, target_col=tc, **kw)


# ---------------------------------------------------------------------------
# Item initialization
# ---------------------------------------------------------------------------

class TestItemInitialization:
    def test_no_piece_starts_with_item(self):
        state = GameState.new_game()
        for row in state.board:
            for piece in row:
                if piece is not None:
                    assert piece.held_item == Item.NONE, (
                        f"{piece.piece_type} at ({piece.row},{piece.col}) starts with {piece.held_item}"
                    )

    def test_exactly_four_hidden_items(self):
        state = GameState.new_game()
        assert len(state.hidden_items) == 4

    def test_thunderstone_always_present(self):
        for _ in range(10):
            state = GameState.new_game()
            items = [h.item for h in state.hidden_items]
            assert Item.THUNDERSTONE in items

    def test_hidden_items_in_tall_grass_rows(self):
        state = GameState.new_game()
        for h in state.hidden_items:
            assert h.row in TALL_GRASS_ROWS, f"hidden item at row {h.row} outside TALL_GRASS_ROWS"

    def test_hidden_items_on_distinct_squares(self):
        state = GameState.new_game()
        squares = [(h.row, h.col) for h in state.hidden_items]
        assert len(squares) == len(set(squares))

    def test_hidden_items_on_empty_squares(self):
        state = GameState.new_game()
        for h in state.hidden_items:
            assert state.board[h.row][h.col] is None

    def test_no_floor_items_at_start(self):
        state = GameState.new_game()
        assert state.floor_items == []

    def test_no_explored_squares_at_start(self):
        state = GameState.new_game()
        assert state.tall_grass_explored == set()


# ---------------------------------------------------------------------------
# Exploration mechanics
# ---------------------------------------------------------------------------

class TestExploration:
    def test_move_to_grass_explores_square(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0)
        gr = min(TALL_GRASS_ROWS)
        move = make_move(1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert (gr, 0) in ns.tall_grass_explored

    def test_second_visit_to_explored_square_does_not_error(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0)
        gr = min(TALL_GRASS_ROWS)
        state.tall_grass_explored.add((gr, 0))
        move = make_move(1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert (gr, 0) in ns.tall_grass_explored

    def test_pokeball_move_does_not_explore(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 1, 0)
        gr = min(TALL_GRASS_ROWS)
        move = make_move(1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert (gr, 0) not in ns.tall_grass_explored

    def test_safetyball_move_does_not_explore(self):
        state = empty_state()
        place(state, PieceType.SAFETYBALL, Team.RED, 1, 0)
        gr = min(TALL_GRASS_ROWS)
        move = make_move(1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert (gr, 0) not in ns.tall_grass_explored


# ---------------------------------------------------------------------------
# Auto-pickup
# ---------------------------------------------------------------------------

class TestAutoPickup:
    def test_empty_handed_piece_picks_up_item(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0)
        state.hidden_items = [HiddenItem(row=2, col=0, item=Item.WATERSTONE)]
        move = make_move(1, 0, ActionType.MOVE, 2, 0)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[2][0].held_item == Item.WATERSTONE
        assert ns.hidden_items == []

    def test_item_removed_from_hidden_after_pickup(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0)
        state.hidden_items = [HiddenItem(row=2, col=0, item=Item.WATERSTONE)]
        move = make_move(1, 0, ActionType.MOVE, 2, 0)
        [(ns, _)] = apply_move(state, move)
        assert len(ns.hidden_items) == 0

    def test_no_item_on_square_leaves_held_item_unchanged(self):
        state = empty_state()
        gr = min(TALL_GRASS_ROWS)
        place(state, PieceType.SQUIRTLE, Team.RED, gr - 1, 0)
        state.hidden_items = []  # no item on destination
        move = make_move(gr - 1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[gr][0].held_item == Item.NONE


# ---------------------------------------------------------------------------
# Overflow
# ---------------------------------------------------------------------------

class TestOverflow:
    def _setup_overflow(self, existing_item: Item, new_item: Item):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0, item=existing_item)
        state.hidden_items = [HiddenItem(row=2, col=0, item=new_item)]
        return state

    def test_overflow_keep_existing(self):
        state = self._setup_overflow(Item.WATERSTONE, Item.FIRESTONE)
        # keep=existing → piece keeps WATERSTONE, FIRESTONE drops at col 1
        move = make_move(1, 0, ActionType.MOVE, 2, 0,
                         overflow_keep='existing', overflow_drop_row=2, overflow_drop_col=1)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[2][0].held_item == Item.WATERSTONE
        assert any(fi.item == Item.FIRESTONE for fi in ns.floor_items)

    def test_overflow_keep_new(self):
        state = self._setup_overflow(Item.WATERSTONE, Item.FIRESTONE)
        move = make_move(1, 0, ActionType.MOVE, 2, 0,
                         overflow_keep='new', overflow_drop_row=2, overflow_drop_col=1)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[2][0].held_item == Item.FIRESTONE
        dropped = [fi for fi in ns.floor_items if fi.item == Item.WATERSTONE]
        assert len(dropped) == 1
        assert dropped[0].row == 2 and dropped[0].col == 1

    def test_overflow_default_keeps_existing(self):
        """No overflow fields (bot path): keep existing, drop new item."""
        state = self._setup_overflow(Item.WATERSTONE, Item.FIRESTONE)
        move = make_move(1, 0, ActionType.MOVE, 2, 0)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[2][0].held_item == Item.WATERSTONE
        assert any(fi.item == Item.FIRESTONE for fi in ns.floor_items)


# ---------------------------------------------------------------------------
# Floor items
# ---------------------------------------------------------------------------

class TestFloorItems:
    def test_floor_item_picked_up_on_move(self):
        state = empty_state()
        gr = min(TALL_GRASS_ROWS)
        place(state, PieceType.SQUIRTLE, Team.RED, gr - 1, 0)
        state.tall_grass_explored.add((gr, 0))  # already explored
        state.floor_items = [FloorItem(row=gr, col=0, item=Item.WATERSTONE)]
        move = make_move(gr - 1, 0, ActionType.MOVE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert ns.board[gr][0].held_item == Item.WATERSTONE
        assert ns.floor_items == []

    def test_pokeball_capture_drops_item(self):
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 3, 3)
        target = place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 4, item=Item.WATERSTONE)
        move = make_move(3, 3, ActionType.ATTACK, 3, 4)
        results = apply_move(state, move)
        capture_state = next(
            (s for s, _ in results if s.board[3][3] is None and s.board[3][4] is None),
            None,
        )
        assert capture_state is not None
        floor = [fi for fi in capture_state.floor_items if fi.item == Item.WATERSTONE]
        assert len(floor) == 1
        assert floor[0].row == 3 and floor[0].col == 4


# ---------------------------------------------------------------------------
# Discharged / expelled Pokemon exploration
# ---------------------------------------------------------------------------

class TestDischargedExploration:
    def test_released_pokemon_explores_grass_square(self):
        state = empty_state(active=Team.RED)
        # Place a Safetyball on a tall grass square with a stored Squirtle
        gr = min(TALL_GRASS_ROWS)
        sb = place(state, PieceType.SAFETYBALL, Team.RED, gr, 0)
        stored_piece = Piece.create(PieceType.SQUIRTLE, Team.RED, gr, 0)
        stored_piece.current_hp = PIECE_STATS[PieceType.SQUIRTLE].max_hp - 10
        sb.stored_piece = stored_piece
        state.hidden_items = [HiddenItem(row=gr, col=0, item=Item.WATERSTONE)]
        # Add a second RED piece so release doesn't leave the board empty for king check
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        move = make_move(gr, 0, ActionType.RELEASE, gr, 0)
        [(ns, _)] = apply_move(state, move)
        assert (gr, 0) in ns.tall_grass_explored


# ---------------------------------------------------------------------------
# player_view_of_state masking
# ---------------------------------------------------------------------------

class TestPlayerViewMasking:
    def test_hidden_items_omitted(self):
        from app.game_logic.serialization import player_view_of_state
        state = GameState.new_game()
        d = player_view_of_state(state, Team.RED, {})
        assert d["hidden_items"] == []

    def test_opponent_held_item_masked(self):
        from app.game_logic.serialization import player_view_of_state
        state = empty_state()
        p = place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 0, item=Item.WATERSTONE)
        d = player_view_of_state(state, Team.RED, {})
        blue_pieces = [x for x in d["board"] if x["team"] == "BLUE"]
        squirtle = next(x for x in blue_pieces if x["piece_type"] == "SQUIRTLE")
        assert squirtle["held_item"] == "UNKNOWN"

    def test_own_held_item_visible(self):
        from app.game_logic.serialization import player_view_of_state
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 1, 0, item=Item.WATERSTONE)
        d = player_view_of_state(state, Team.RED, {})
        red_pieces = [x for x in d["board"] if x["team"] == "RED"]
        squirtle = next(x for x in red_pieces if x["piece_type"] == "SQUIRTLE")
        assert squirtle["held_item"] == "WATERSTONE"

    def test_floor_items_visible_to_both(self):
        from app.game_logic.serialization import player_view_of_state
        state = empty_state()
        state.floor_items = [FloorItem(row=3, col=3, item=Item.FIRESTONE)]
        for team in (Team.RED, Team.BLUE):
            d = player_view_of_state(state, team, {})
            assert len(d["floor_items"]) == 1
            assert d["floor_items"][0]["item"] == "FIRESTONE"

    def test_tall_grass_explored_visible_to_both(self):
        from app.game_logic.serialization import player_view_of_state
        state = empty_state()
        state.tall_grass_explored = {(3, 3), (4, 5)}
        for team in (Team.RED, Team.BLUE):
            d = player_view_of_state(state, team, {})
            squares = {tuple(sq) for sq in d["tall_grass_explored"]}
            assert (3, 3) in squares and (4, 5) in squares

    def test_opponent_none_item_not_masked(self):
        """Pieces holding NONE should not show 'UNKNOWN'."""
        from app.game_logic.serialization import player_view_of_state
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.BLUE, 5, 0)  # held_item = NONE
        d = player_view_of_state(state, Team.RED, {})
        blue_pieces = [x for x in d["board"] if x["team"] == "BLUE"]
        squirtle = next(x for x in blue_pieces if x["piece_type"] == "SQUIRTLE")
        assert squirtle["held_item"] == "NONE"
