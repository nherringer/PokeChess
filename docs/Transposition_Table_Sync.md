# Transposition Table Sync Design

**Status:** Approved, pre-implementation  
**Authors:** nherringer  
**Audience:** ML bot team

---

## Overview

The transposition table (TT) maps Zobrist hashes to `(wins, visits)` statistics accumulated across games. It is the bot's inter-game learning mechanism. This document covers how the TT is stored locally, backed up to S3, and restored on startup.

The TT is **local-first**: the bot reads and writes a binary file on disk during normal operation. S3 is a backup target — it is written to periodically and read from only when no local file exists.

---

## Background

### Current state

`bot/transposition.py` implements `TranspositionTable` with `save(path)` and `load(path)` methods that read/write a 16-byte-per-entry binary format. These already work correctly for local persistence. The gap is the remote backup layer.

### What we need

- **On startup:** load TT from local disk if it exists; otherwise pull from S3; otherwise start fresh
- **Periodic backup:** upload local TT to S3 every 50 requests (half-moves served across all games)
- **Concurrency safety:** serialize uploads within the process to prevent a backup from racing with itself

---

## TT Versioning

The S3 key includes a version integer: `tt_v{TT_VERSION}.bin`.

`TT_VERSION` is a module-level constant in `bot/tt_store.py`. When a rules change invalidates existing stats, bump this constant and redeploy. The old key is left in S3 (cheap storage, useful audit trail) and the bot starts fresh with an empty TT under the new key.

No metadata or header is stored inside the binary file itself — versioning lives entirely in the key name.

---

## Files

| File | Purpose |
|---|---|
| `bot/tt_store.py` | S3 client wrapper + background backup queue |
| `tests/test_tt_store.py` | Mocked boto3 tests |

---

## `bot/tt_store.py` Design

### `TTStore` class

Thin wrapper around boto3 for download and upload.

```
TTStore(bucket: str, key: str):
  download(local_path: str) → bool
    # Downloads S3 key to local_path.
    # Returns False (no-op) if the key does not exist — fresh-start case.
    # Raises on all other S3 errors.

  upload(local_path: str) → None
    # Uploads local_path to S3 key.
```

### `TTSyncQueue` class

A background thread that serializes backup operations. The main thread enqueues backup requests; the worker processes them one at a time.

```
TTSyncQueue(tt: TranspositionTable, store: TTStore, local_path: str):
  enqueue() → None
    # Puts a backup request on the queue (non-blocking).
    # If a backup is already queued but not yet started, a second enqueue is a no-op
    # (deduplication) to avoid piling up redundant work.

  drain() → None
    # Blocks until the queue is empty and the worker is idle.
    # Called via atexit on process shutdown to prevent exiting mid-backup.

  _worker() → None
    # Background thread body. Loops forever, processing one backup per iteration:
    #   1. Call tt.save(local_path) to flush the in-memory TT to disk
    #   2. Call store.upload(local_path) to push the file to S3
```

Since there is one bot API process and S3 is a backup (not a shared merge target), no download-merge cycle is needed. The local TT is always authoritative; the backup operation is a straightforward save-then-upload.

---

## Startup sequence

On process startup, the bot resolves its initial TT state using the following priority order:

```
1. Local file exists at POKECHESS_TT_LOCAL_PATH?
      YES → load into global_tt, done.
       NO → continue

2. S3 key tt_v{TT_VERSION}.bin exists in POKECHESS_TT_BUCKET?
      YES → download to POKECHESS_TT_LOCAL_PATH, load into global_tt, done.
       NO → continue

3. Start with an empty global_tt.
      (First backup will create the S3 key.)
```

This ensures the bot never fails to start due to a missing TT, and that a locally cached file is always preferred over a network fetch.

---

## Integration with the Bot API

See `docs/Bot_API_Design.md` for the full API design. TT sync integration points:

| Trigger | Action |
|---|---|
| `bot/server.py` startup | Run startup sequence above; start `TTSyncQueue` worker thread |
| `request_count % 50 == 0` | `sync_queue.enqueue()` |
| Process shutdown (atexit) | `sync_queue.drain()` |

`request_count` is a global counter incremented on every `POST /move` request. A backup fires at every 50th request regardless of which game the move belonged to. Exact alignment to game boundaries is not required.

The app **does not** trigger TT backups and has no visibility into the TT. All persistence is the engine's internal concern. `Dockerfile.engine` notes a `POST /backup` endpoint; if implemented, it is for ops/admin use only (e.g. forcing a flush before a deploy) — not called by the app.

---

## Configuration

The following should be configurable via environment variables (no hardcoded values in source):

| Variable | Purpose |
|---|---|
| `POKECHESS_TT_LOCAL_PATH` | Path to the local TT binary file |
| `POKECHESS_TT_BUCKET` | S3 bucket name |
| `POKECHESS_TT_VERSION` | TT version integer (overrides compiled-in default) |
| `AWS_DEFAULT_REGION` | Standard boto3 env var |
| `AWS_ACCESS_KEY_ID` | Standard boto3 env var |
| `AWS_SECRET_ACCESS_KEY` | Standard boto3 env var |

> **Naming note:** `docker-compose.yml` has a TODO comment that refers to this bucket variable as `S3_TREE_BUCKET`. That comment predates this design doc. `POKECHESS_TT_BUCKET` is the authoritative name — update the docker-compose comment when implementing `bot/tt_store.py`.

---

## Verification

| Test | Method |
|---|---|
| Local-first startup | Local file present → S3 never contacted |
| S3 fallback startup | No local file, S3 key exists → downloaded and loaded correctly |
| Fresh start | No local file, S3 key absent → `global_tt` starts empty; no error |
| Backup round-trip | Save TT → upload → download → load → stats match original |
| Queue deduplication | Enqueueing twice while worker is busy results in one upload, not two |
| Drain on shutdown | `drain()` blocks until in-flight backup completes |
| Version isolation | Changing `TT_VERSION` targets a different S3 key; old stats not loaded |
