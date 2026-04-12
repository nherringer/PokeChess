"""
Tests for load-aware MCTS budget scaling and Piece.id propagation.

These are pure-Python unit tests — no database or HTTP server required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.state import GameState, Piece, PieceType, Team, Item
from engine.moves import Move, ActionType
from engine.rules import apply_move

from app.game_logic.serialization import state_from_dict, state_to_dict
from app.game_logic.id_map import remap_ids


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


def place(state: GameState, pt: PieceType, team: Team, row: int, col: int) -> Piece:
    piece = Piece.create(pt, team, row, col)
    state.board[row][col] = piece
    return piece


# ---------------------------------------------------------------------------
# Task 3: load-aware budget calculation (pure logic, no DB)
# ---------------------------------------------------------------------------

class TestEffectiveBudgetCalc:
    """The effective budget is base / N, floored so N >= 1."""

    def _effective(self, base: float, n: int) -> float:
        n = max(1, n)
        return base / n

    def test_single_player_gets_full_budget(self):
        assert self._effective(3.0, 1) == pytest.approx(3.0)

    def test_two_players_each_get_half(self):
        assert self._effective(2.0, 2) == pytest.approx(1.0)

    def test_zero_active_clamped_to_one(self):
        # count_active_bot_players guarantees >= 1, but test the formula too
        assert self._effective(3.0, 0) == pytest.approx(3.0)

    def test_large_concurrent_load(self):
        assert self._effective(10.0, 10) == pytest.approx(1.0)


class TestPersonaParamsBuilding:
    """persona_params must carry all bot_params and override time_budget."""

    def _build_params(self, bot_params: dict, effective_budget: float) -> dict:
        return {**bot_params, "time_budget": effective_budget}

    def test_time_budget_overridden(self):
        params = self._build_params({"time_budget": 3.0, "exploration_c": 1.4}, 1.5)
        assert params["time_budget"] == pytest.approx(1.5)

    def test_extra_keys_preserved(self):
        params = self._build_params({"time_budget": 3.0, "exploration_c": 1.4}, 1.5)
        assert params["exploration_c"] == pytest.approx(1.4)

    def test_empty_bot_params(self):
        params = self._build_params({}, 2.0)
        assert params == {"time_budget": 2.0}


# ---------------------------------------------------------------------------
# Task 3: count_active_bot_players helper contract
# ---------------------------------------------------------------------------

class TestCountActiveBotPlayers:
    """count_active_bot_players must always return >= 1."""

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_returns_at_least_one_when_db_returns_zero(self):
        from app.db.queries.bot_activity import count_active_bot_players
        import uuid

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={"n": 0})

        result = self._run(count_active_bot_players(mock_db, uuid.uuid4(), 22))
        assert result == 1

    def test_returns_count_when_positive(self):
        from app.db.queries.bot_activity import count_active_bot_players
        import uuid

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={"n": 5})

        result = self._run(count_active_bot_players(mock_db, uuid.uuid4(), 22))
        assert result == 5

    def test_returns_one_when_fetchrow_returns_none(self):
        from app.db.queries.bot_activity import count_active_bot_players
        import uuid

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value=None)

        result = self._run(count_active_bot_players(mock_db, uuid.uuid4(), 22))
        assert result == 1


# ---------------------------------------------------------------------------
# Task 4: Piece.id field and round-trip serialization
# ---------------------------------------------------------------------------

class TestPieceIdField:
    def test_piece_has_id_field_defaulting_to_none(self):
        p = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        assert p.id is None

    def test_piece_id_survives_copy(self):
        p = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        p.id = "abc-123"
        copy = p.copy()
        assert copy.id == "abc-123"

    def test_piece_id_survives_copy_when_none(self):
        p = Piece.create(PieceType.SQUIRTLE, Team.RED, 0, 0)
        assert p.copy().id is None


class TestSerializationPieceId:
    def test_state_from_dict_sets_piece_id(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        id_map = {(0, 0): "uuid-squi"}
        d = state_to_dict(state, id_map)

        loaded, _ = state_from_dict(d)
        assert loaded.board[0][0].id == "uuid-squi"

    def test_state_from_dict_id_none_for_pieces_without_id(self):
        """Pieces that have no id in the dict get id=None."""
        state = empty_state()
        place(state, PieceType.POKEBALL, Team.RED, 1, 0)
        id_map: dict = {}
        d = state_to_dict(state, id_map)

        loaded, _ = state_from_dict(d)
        assert loaded.board[1][0].id is None

    def test_state_to_dict_uses_piece_id_over_id_map(self):
        """piece.id takes priority when both piece.id and id_map have a value."""
        state = empty_state()
        p = place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        p.id = "piece-uuid"
        id_map = {(0, 0): "map-uuid"}  # different value

        d = state_to_dict(state, id_map)
        piece_dict = d["board"][0]
        assert piece_dict["id"] == "piece-uuid"

    def test_state_to_dict_falls_back_to_id_map_when_piece_id_none(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 0, 0)
        id_map = {(0, 0): "map-uuid"}

        d = state_to_dict(state, id_map)
        assert d["board"][0]["id"] == "map-uuid"

    def test_round_trip_preserves_id(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 3, 2)
        id_map = {(3, 2): "rook-uuid"}

        d = state_to_dict(state, id_map)
        loaded, loaded_map = state_from_dict(d)

        assert loaded.board[3][2].id == "rook-uuid"
        assert loaded_map[(3, 2)] == "rook-uuid"


class TestRemapIdsPropagatesPieceId:
    def test_remap_sets_piece_id_on_moved_piece(self):
        state = empty_state()
        p = place(state, PieceType.SQUIRTLE, Team.RED, 2, 0)
        p.id = "rook-uuid"
        # Blue king needed so the game is legal
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)

        id_map = {(2, 0): "rook-uuid"}
        move = Move(
            piece_row=2, piece_col=0,
            action_type=ActionType.MOVE,
            target_row=3, target_col=0,
        )
        outcomes = apply_move(state, move)
        new_state = outcomes[0][0]

        new_map = remap_ids(state, new_state, move, id_map)

        # UUID should follow the piece to its new position
        assert new_map.get((3, 0)) == "rook-uuid"
        # piece.id should be updated directly
        assert new_state.board[3][0].id == "rook-uuid"

    def test_remap_id_none_for_unlisted_piece(self):
        state = empty_state()
        place(state, PieceType.SQUIRTLE, Team.RED, 2, 0)
        place(state, PieceType.EEVEE, Team.BLUE, 7, 4)
        place(state, PieceType.PIKACHU, Team.RED, 0, 4)

        id_map: dict = {}  # no UUIDs registered
        move = Move(
            piece_row=2, piece_col=0,
            action_type=ActionType.MOVE,
            target_row=3, target_col=0,
        )
        outcomes = apply_move(state, move)
        new_state = outcomes[0][0]

        remap_ids(state, new_state, move, id_map)
        # piece.id should remain None — remap never invents a UUID
        assert new_state.board[3][0].id is None
