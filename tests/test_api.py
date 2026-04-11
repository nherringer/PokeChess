"""
Tests for bot/server.py — FastAPI bot API endpoint.

MCTS and TTSyncQueue are mocked so tests run fast without real searches.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

from engine.state import GameState
from engine.moves import Move, ActionType


# ---------------------------------------------------------------------------
# Helpers — build a valid FEN dict from the starting position
# ---------------------------------------------------------------------------

def _new_game_dict() -> dict:
    """Return a minimal valid FEN dict for the new-game starting position."""
    state = GameState.new_game()
    board = []
    for row in state.board:
        for piece in row:
            if piece is not None:
                pd: dict[str, Any] = {
                    "piece_type": piece.piece_type.name,
                    "team": piece.team.name,
                    "row": piece.row,
                    "col": piece.col,
                    "current_hp": piece.current_hp,
                    "held_item": piece.held_item.name,
                    "stored_piece": None,
                }
                board.append(pd)
    return {
        "active_player": "RED",
        "turn_number": 1,
        "has_traded": {"RED": False, "BLUE": False},
        "foresight_used_last_turn": {"RED": False, "BLUE": False},
        "pending_foresight": {"RED": None, "BLUE": None},
        "board": board,
    }


def _fake_move() -> Move:
    return Move(
        piece_row=1, piece_col=0,
        action_type=ActionType.MOVE,
        target_row=2, target_col=0,
    )


# ---------------------------------------------------------------------------
# Fixture — fresh TestClient with mocked MCTS and TTSyncQueue per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_and_mocks():
    """
    Reload server module so global state (request_count, etc.) starts fresh.
    Patches MCTS and TTSyncQueue before the app lifespan runs.
    """
    fake_move = _fake_move()
    mock_mcts_instance = MagicMock()
    mock_mcts_instance.select_move.return_value = fake_move

    mock_mcts_cls = MagicMock(return_value=mock_mcts_instance)
    mock_sync_queue = MagicMock()
    mock_sync_queue_cls = MagicMock(return_value=mock_sync_queue)

    # Remove cached module so state resets
    for mod_name in list(sys.modules.keys()):
        if "bot.server" in mod_name:
            del sys.modules[mod_name]

    with patch("bot.mcts.MCTS", mock_mcts_cls), \
         patch("bot.tt_store.TTSyncQueue", mock_sync_queue_cls):
        # Re-import server *inside* the patch context so module-level code
        # (lock creation, etc.) uses fresh state.
        import bot.server as server_mod

        # Patch the names *in the server module's namespace* as well,
        # since it imports MCTS and TTSyncQueue directly.
        server_mod.MCTS = mock_mcts_cls
        server_mod.TTSyncQueue = mock_sync_queue_cls

        # Reset module-level counters
        server_mod.request_count = 0
        server_mod.global_tt = server_mod.TranspositionTable()
        server_mod.sync_queue = mock_sync_queue

        with TestClient(server_mod.app) as client:
            yield client, mock_mcts_cls, mock_sync_queue, server_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client_and_mocks):
        client, *_ = client_and_mocks
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestMoveEndpointHappyPath:
    def test_returns_flat_move_dict(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 1.0},
        }
        resp = client.post("/move", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # All expected keys must be present at the top level (flat, not nested)
        for key in ("piece_row", "piece_col", "action_type", "target_row", "target_col",
                    "secondary_row", "secondary_col", "move_slot"):
            assert key in data, f"Missing key: {key}"
        assert data["action_type"] == "MOVE"
        assert data["piece_row"] == 1
        assert data["piece_col"] == 0
        assert data["target_row"] == 2
        assert data["target_col"] == 0
        assert data["secondary_row"] is None
        assert data["secondary_col"] is None
        assert data["move_slot"] is None

    def test_time_budget_forwarded_to_mcts(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 2.5},
        }
        client.post("/move", json=payload)
        _, kwargs = mock_mcts_cls.call_args
        assert kwargs.get("time_budget") == pytest.approx(2.5)

    def test_exploration_c_forwarded_when_present(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 1.0, "exploration_c": 1.414},
        }
        client.post("/move", json=payload)
        _, kwargs = mock_mcts_cls.call_args
        assert "exploration_c" in kwargs
        assert kwargs["exploration_c"] == pytest.approx(1.414)

    def test_exploration_c_omitted_when_absent(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 1.0},
        }
        client.post("/move", json=payload)
        _, kwargs = mock_mcts_cls.call_args
        assert "exploration_c" not in kwargs, (
            "exploration_c should NOT be passed when absent from persona_params"
        )


class TestTimeBudgetClamping:
    def test_time_budget_clamped_above(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 999.0},
        }
        client.post("/move", json=payload)
        _, kwargs = mock_mcts_cls.call_args
        assert kwargs["time_budget"] <= 10.0

    def test_time_budget_clamped_below(self, client_and_mocks):
        client, mock_mcts_cls, *_ = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 0.0},
        }
        client.post("/move", json=payload)
        _, kwargs = mock_mcts_cls.call_args
        assert kwargs["time_budget"] >= 0.1


class TestRequestCounterAndEnqueue:
    def test_enqueue_called_at_50_requests(self, client_and_mocks):
        client, mock_mcts_cls, mock_sync_queue, server_mod = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 0.1},
        }
        # 49 requests — no enqueue yet
        for _ in range(49):
            resp = client.post("/move", json=payload)
            assert resp.status_code == 200
        mock_sync_queue.enqueue.assert_not_called()

        # 50th request — enqueue fires
        resp = client.post("/move", json=payload)
        assert resp.status_code == 200
        mock_sync_queue.enqueue.assert_called_once()

    def test_enqueue_not_called_before_50_requests(self, client_and_mocks):
        client, mock_mcts_cls, mock_sync_queue, server_mod = client_and_mocks
        payload = {
            "state": _new_game_dict(),
            "persona_params": {"time_budget": 0.1},
        }
        for _ in range(49):
            client.post("/move", json=payload)
        mock_sync_queue.enqueue.assert_not_called()


class TestMalformedState:
    def test_missing_required_field_returns_422(self, client_and_mocks):
        client, *_ = client_and_mocks
        # State missing 'active_player' and 'board' — should be rejected
        payload = {
            "state": {"invalid": "data"},
            "persona_params": {"time_budget": 1.0},
        }
        resp = client.post("/move", json=payload)
        assert resp.status_code == 422

    def test_empty_state_returns_422(self, client_and_mocks):
        client, *_ = client_and_mocks
        payload = {
            "state": {},
            "persona_params": {"time_budget": 1.0},
        }
        resp = client.post("/move", json=payload)
        assert resp.status_code == 422

    def test_unknown_piece_type_returns_422(self, client_and_mocks):
        client, *_ = client_and_mocks
        bad_state = _new_game_dict()
        # Corrupt the first piece's type
        bad_state["board"][0]["piece_type"] = "NOT_A_REAL_POKEMON"
        payload = {
            "state": bad_state,
            "persona_params": {"time_budget": 1.0},
        }
        resp = client.post("/move", json=payload)
        assert resp.status_code == 422


class TestS3StartupErrorFallback:
    """Engine must start and serve requests even when S3 is unreachable."""

    def test_s3_error_on_startup_falls_back_to_empty_tt(self):
        """If S3 download raises during startup, the engine starts with an empty TT."""
        import os

        for mod_name in list(sys.modules.keys()):
            if "bot.server" in mod_name:
                del sys.modules[mod_name]

        mock_mcts_instance = MagicMock()
        mock_mcts_instance.select_move.return_value = _fake_move()
        mock_mcts_cls = MagicMock(return_value=mock_mcts_instance)
        mock_sync_queue = MagicMock()
        mock_sync_queue_cls = MagicMock(return_value=mock_sync_queue)

        # Simulate an S3 store that raises on download (e.g. wrong bucket/credentials).
        mock_store_instance = MagicMock()
        mock_store_instance.download.side_effect = RuntimeError("S3 unreachable")
        mock_store_cls = MagicMock(return_value=mock_store_instance)

        env_patch = patch.dict(os.environ, {"POKECHESS_TT_BUCKET": "some-bucket"})

        with patch("bot.mcts.MCTS", mock_mcts_cls), \
             patch("bot.tt_store.TTSyncQueue", mock_sync_queue_cls), \
             patch("bot.tt_store.TTStore", mock_store_cls), \
             env_patch:
            import bot.server as server_mod
            server_mod.MCTS = mock_mcts_cls
            server_mod.TTSyncQueue = mock_sync_queue_cls
            server_mod.TTStore = mock_store_cls
            server_mod.request_count = 0
            server_mod.global_tt = server_mod.TranspositionTable()
            server_mod.sync_queue = mock_sync_queue

            with TestClient(server_mod.app) as client:
                # Engine must be reachable despite the S3 failure.
                assert client.get("/health").status_code == 200
                # And must serve move requests normally.
                resp = client.post("/move", json={
                    "state": _new_game_dict(),
                    "persona_params": {"time_budget": 0.1},
                })
                assert resp.status_code == 200
