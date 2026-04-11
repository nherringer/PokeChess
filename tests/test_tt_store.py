"""
Tests for bot/tt_store.py.

TTStore accepts an optional s3_client kwarg for dependency injection, so no
real boto3 install is required.  ClientError is simulated by a local stub that
mirrors the .response dict shape botocore uses.
"""

from __future__ import annotations

import os
import shutil
import threading
from unittest.mock import MagicMock, call

import pytest

from bot.transposition import TranspositionTable
from bot.tt_store import TTStore, TTSyncQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeClientError(Exception):
    """Minimal stand-in for botocore.exceptions.ClientError."""
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code, "Message": "test"}}
        super().__init__(code)


def _make_store(mock_s3, bucket="my-bucket", key="tt_v1.bin") -> TTStore:
    return TTStore(bucket=bucket, key=key, s3_client=mock_s3)


# ---------------------------------------------------------------------------
# TTStore.download
# ---------------------------------------------------------------------------

class TestTTStoreDownload:

    def test_returns_false_for_no_such_key(self, tmp_path):
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = _FakeClientError("NoSuchKey")
        store = _make_store(mock_s3)

        result = store.download(str(tmp_path / "tt.bin"))

        assert result is False
        assert not (tmp_path / "tt.bin").exists()

    def test_returns_false_for_404(self, tmp_path):
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = _FakeClientError("404")
        store = _make_store(mock_s3)

        result = store.download(str(tmp_path / "tt.bin"))

        assert result is False

    def test_raises_on_unexpected_error(self, tmp_path):
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = _FakeClientError("AccessDenied")
        store = _make_store(mock_s3)

        with pytest.raises(_FakeClientError):
            store.download(str(tmp_path / "tt.bin"))

    def test_success_returns_true(self, tmp_path):
        local = str(tmp_path / "tt.bin")
        mock_s3 = MagicMock()
        store = _make_store(mock_s3)

        result = store.download(local)

        assert result is True
        mock_s3.download_file.assert_called_once_with("my-bucket", "tt_v1.bin", local)


# ---------------------------------------------------------------------------
# TTStore.upload
# ---------------------------------------------------------------------------

class TestTTStoreUpload:

    def test_upload_calls_s3_with_correct_args(self, tmp_path):
        local = str(tmp_path / "tt.bin")
        with open(local, "wb") as f:
            f.write(b"\x00")

        mock_s3 = MagicMock()
        store = _make_store(mock_s3)
        store.upload(local)

        mock_s3.upload_file.assert_called_once_with(local, "my-bucket", "tt_v1.bin")


# ---------------------------------------------------------------------------
# Local-first startup
# ---------------------------------------------------------------------------

class TestLocalFirstStartup:

    def test_no_download_if_local_file_exists(self, tmp_path):
        """Startup logic: skip S3 download when a local TT file already exists."""
        local = str(tmp_path / "tt.bin")
        tt = TranspositionTable()
        tt.update(123, 1.0)
        tt.save(local)
        assert os.path.exists(local)

        mock_s3 = MagicMock()
        store = _make_store(mock_s3)

        # Mirrors the startup sequence in bot/server.py
        if not os.path.exists(local):
            store.download(local)

        mock_s3.download_file.assert_not_called()


# ---------------------------------------------------------------------------
# TTSyncQueue — deduplication
# ---------------------------------------------------------------------------

class TestTTSyncQueueDedup:

    def test_double_enqueue_results_in_one_upload(self, tmp_path):
        """Two enqueues before the worker dequeues → exactly one upload."""
        local = str(tmp_path / "tt.bin")
        tt = TranspositionTable()
        tt.update(2, 1.0)
        tt.save(local)

        worker_gate = threading.Event()
        original_worker = TTSyncQueue._worker

        def held_worker(self_inner):
            worker_gate.wait()
            original_worker(self_inner)

        upload_count = [0]
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = lambda path, bucket, key: upload_count.__setitem__(0, upload_count[0] + 1)

        store = _make_store(mock_s3)
        with __import__("unittest.mock", fromlist=["patch"]).patch.object(TTSyncQueue, "_worker", held_worker):
            sync = TTSyncQueue(tt, store, local)
            sync.enqueue()
            sync.enqueue()  # no-op — _pending is already True
            assert sync._queue.qsize() == 1, "Dedup failed: queue should have exactly 1 item"

        worker_gate.set()
        sync.drain()

        assert upload_count[0] == 1, "Expected exactly 1 upload for 2 rapid enqueues"


# ---------------------------------------------------------------------------
# TTSyncQueue — drain blocks until backup completes
# ---------------------------------------------------------------------------

class TestTTSyncQueueDrain:

    def test_drain_blocks_until_worker_done(self, tmp_path):
        local = str(tmp_path / "tt.bin")
        tt = TranspositionTable()
        tt.update(42, 1.0)
        tt.save(local)

        gate = threading.Event()
        worker_started = threading.Event()

        mock_s3 = MagicMock()

        def blocking_upload(path, bucket, key):
            worker_started.set()
            gate.wait()

        mock_s3.upload_file.side_effect = blocking_upload

        store = _make_store(mock_s3)
        sync = TTSyncQueue(tt, store, local)
        sync.enqueue()

        assert worker_started.wait(timeout=2.0), "Worker never started"

        drain_done = threading.Event()

        def run_drain():
            sync.drain()
            drain_done.set()

        drain_thread = threading.Thread(target=run_drain, daemon=True)
        drain_thread.start()

        drain_done.wait(timeout=0.15)
        assert not drain_done.is_set(), "drain() returned before backup finished"

        gate.set()
        assert drain_done.wait(timeout=2.0), "drain() never returned after backup completed"


# ---------------------------------------------------------------------------
# Round-trip: save → upload → download → load
# ---------------------------------------------------------------------------

class TestTTRoundTrip:

    def test_stats_survive_upload_download_cycle(self, tmp_path):
        save_path = str(tmp_path / "tt_save.bin")
        load_path = str(tmp_path / "tt_load.bin")

        tt_orig = TranspositionTable()
        tt_orig.update(0xDEADBEEF, 3.0)
        tt_orig.update(0xDEADBEEF, 1.0)  # wins=4.0, visits=2
        tt_orig.update(0xCAFEBABE, 0.5)  # wins=0.5, visits=1
        tt_orig.save(save_path)

        uploaded: list[str] = []

        def fake_upload(path, bucket, key):
            uploaded.append(path)

        def fake_download(bucket, key, dest):
            shutil.copy(save_path, dest)

        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = fake_upload
        mock_s3.download_file.side_effect = fake_download

        store = _make_store(mock_s3)
        store.upload(save_path)
        result = store.download(load_path)

        assert uploaded == [save_path]
        assert result is True
        assert os.path.exists(load_path)

        tt_loaded = TranspositionTable()
        tt_loaded.load(load_path)

        wins_beef, visits_beef = tt_loaded.get(0xDEADBEEF)
        wins_cafe, visits_cafe = tt_loaded.get(0xCAFEBABE)

        assert visits_beef == 2
        assert abs(wins_beef - 4.0) < 1e-5
        assert visits_cafe == 1
        assert abs(wins_cafe - 0.5) < 1e-5
