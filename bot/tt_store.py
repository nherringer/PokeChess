"""
S3 backup layer for the TranspositionTable.

TTStore      — thin boto3 wrapper for download/upload of a single S3 key.
TTSyncQueue  — background daemon thread that serializes TT save+upload requests.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.transposition import TranspositionTable

logger = logging.getLogger(__name__)


class TTStore:
    """Thin boto3 wrapper for a single S3 key."""

    def __init__(self, bucket: str, key: str, *, s3_client=None) -> None:
        self._bucket = bucket
        self._key = key
        if s3_client is not None:
            self._s3 = s3_client
        else:
            import boto3 as _boto3
            self._s3 = _boto3.client("s3")

    def download(self, local_path: str) -> bool:
        """Download the S3 key to local_path.

        Returns False (no file written) if the key does not exist.
        Raises on all other S3 errors.
        """
        try:
            self._s3.download_file(self._bucket, self._key, local_path)
            return True
        except Exception as exc:
            # boto3 raises botocore.exceptions.ClientError, which carries a
            # .response dict.  Duck-type the check so botocore need not be
            # imported at module load time (keeps the engine container's deps
            # minimal and makes unit-testing without a real boto3 install easy).
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                return False
            raise

    def upload(self, local_path: str) -> None:
        """Upload local_path to the S3 key. Raises on failure."""
        self._s3.upload_file(local_path, self._bucket, self._key)


class TTSyncQueue:
    """Background daemon thread that serializes TT save+upload operations.

    Usage::

        store = TTStore(bucket, key)
        q = TTSyncQueue(tt, store, local_path)
        q.enqueue()      # non-blocking; triggers save+upload in background
        q.drain()        # block until the worker is idle (e.g. at atexit)
    """

    def __init__(
        self,
        tt: "TranspositionTable",
        store: TTStore,
        local_path: str,
    ) -> None:
        self._tt = tt
        self._store = store
        self._local_path = local_path

        # Queue carries sentinel items — the value doesn't matter, only presence.
        self._queue: queue.Queue[object] = queue.Queue()

        # True while a backup request has been put on the queue but the worker
        # has not yet dequeued it.  Protected via threading.Lock so that
        # enqueue() and the worker's clear step are race-free.
        self._pending = False
        self._pending_lock = threading.Lock()

        # Event that the worker sets when it finishes each backup cycle and is
        # blocking on the next queue.get().  drain() waits on this.
        self._idle = threading.Event()
        self._idle.set()  # worker starts idle

        self._thread = threading.Thread(target=self._worker, daemon=True, name="TTSyncQueue")
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self) -> None:
        """Queue a backup request (non-blocking).

        If a backup is already queued but not yet started, this is a no-op.
        """
        with self._pending_lock:
            if self._pending:
                return
            self._pending = True
            # Clear idle *inside* the lock before putting to the queue so that
            # a concurrent drain() cannot return between the put and the clear.
            self._idle.clear()
        self._queue.put(True)

    def drain(self) -> None:
        """Block until the queue is empty AND the worker is idle.

        Intended for atexit to ensure no backup is abandoned on shutdown.
        """
        self._idle.wait()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        while True:
            # Block until a request arrives.
            self._queue.get()

            # Clear the dedup flag now — a new enqueue() is allowed to queue
            # a fresh backup while this one is in progress.
            with self._pending_lock:
                self._pending = False

            try:
                self._tt.save(self._local_path)
                self._store.upload(self._local_path)
            except Exception:
                logger.exception("TTSyncQueue: backup failed")
            finally:
                self._queue.task_done()
                # Signal idle only after task_done so that drain() doesn't
                # return before task_done is called.
                if self._queue.empty():
                    self._idle.set()
