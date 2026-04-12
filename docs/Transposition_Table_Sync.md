# Transposition Table Sync Design

**Status:** Fully implemented (phases 1–3 + fixed-size array TT refactor)  
**Authors:** nherringer  
**Audience:** ML bot team

---

## Overview

The transposition table (TT) maps Zobrist hashes to `(wins, visits)` statistics accumulated across games. It is the bot's inter-game learning mechanism. This document covers how the TT is stored locally, backed up to S3, restored on startup, and how the in-memory representation is designed to avoid running out of RAM.

The TT is **local-first**: the bot reads and writes a binary file on disk during normal operation. S3 is a backup target — it is written to periodically and read from only when no local file exists.

---

## Background

### Current state

`bot/transposition.py` implements `TranspositionTable` with `save(path)` and `load(path)` methods that read/write a 16-byte-per-entry binary format. These already work correctly for local persistence. `bot/tt_store.py` implements `TTStore` (S3 upload/download) and `TTSyncQueue` (background backup thread). `bot/server.py` wires these together at startup and triggers periodic backups.

### What we need

- **On startup:** load TT from local disk if it exists; otherwise pull from S3; otherwise start fresh
- **Periodic backup:** upload local TT to S3 every 50 requests (half-moves served across all games)
- **Concurrency safety:** serialize uploads within the process to prevent a backup from racing with itself
- **Bounded memory:** the TT will grow to millions of entries quickly; the in-memory representation must be designed to avoid OOM kills

---

## TT Implementation Design

This section covers decisions about the in-memory data structure for the TT: how large it will grow, why the default Python dict is insufficient at scale, how a fixed-size array eliminates the RAM problem, how eviction works, and why the eviction policy for PokeChess must differ from what chess engines use.

### TT size and growth characteristics

Empirically, starting from an empty TT, **5–10 games (~300 half-moves) produces approximately 5 million TT entries**. This is faster than you might expect from chess, for two reasons:

1. **High branching factor.** A typical chess position has ~30 legal moves; PokeChess has substantially more due to multi-type piece moves, attack/pokeball options, and foresight. MCTS explores more unique states per rollout.
2. **Exponential-looking early growth.** When the TT is empty, nearly every position encountered is new, so almost every rollout populates the table. Growth slows as the bot revisits known positions, but this takes hundreds of games to become dominant. From the outside, the first few hundred games look like exponential growth even though the asymptotic behavior is logarithmic.

The expected plateau is **hundreds of millions of entries** — representing the set of common mid-game positions the bot encounters across its lifetime. At that point, almost every position during a game is already in the table, new entries are rare, and the TT stabilizes.

### Memory model: Python dict vs fixed-size array

#### Why the Python dict is a problem

`TranspositionTable` currently uses a `dict[int, tuple[float, int]]` internally. Python dicts have excellent average-case O(1) lookup and insertion, but the CPython object model imposes heavy per-entry memory overhead:

| Object | Memory |
|---|---|
| `int` key (Zobrist hash) | ~28 bytes |
| `float` wins value | ~24 bytes |
| `int` visits value | ~28 bytes |
| `tuple` wrapper for `(wins, visits)` | ~56 bytes |
| Dict slot overhead | ~20 bytes |
| **Total per entry** | **~156 bytes** |

At 5 million entries after 5–10 games, this is already **~750 MB to 1 GB of RAM**. At 50 million entries it would exceed 7 GB — far beyond any container we would run this in.

The O(1) time complexity of dict lookup is a property of *time*, not space. The table still requires one Python object per entry, and those objects are expensive. O(1) insert means insertions don't slow down as the table grows; it says nothing about how much RAM each insertion consumes.

#### The fixed-size array solution

`array.array` stores raw primitive values with no Python object wrapper per element — it is equivalent to a C array of primitives. The layout for our TT is three parallel arrays:

```
_hashes:  array('Q', ...)   # uint64 — one Zobrist hash per slot
_wins:    array('f', ...)   # float32 — accumulated wins
_visits:  array('I', ...)   # uint32 — visit count
```

Each slot is exactly `8 + 4 + 4 = 16 bytes`. At 64 million slots this is exactly **1 GB of RAM**, allocated once at startup and never growing.

The lookup is: `slot = hash % table_size`. This is O(1) in both time and memory. There is no dynamic allocation per entry — the 1 GB is the total memory cost for the lifetime of the process.

At 64 million slots, 50 million entries occupy ~78% of the table. At 128 million slots (~2 GB) you can hold ~100 million entries before significant collision degradation. The appropriate size depends on the deployment instance's RAM budget and can be configured via an environment variable.

**Comparison:**

| Implementation | Bytes per entry | 64M entries RAM | Memory is fixed? |
|---|---|---|---|
| Python dict | ~156 bytes | ~10 GB | No — grows with insertions |
| `array.array` (fixed-size) | 16 bytes | 1 GB | Yes — allocated at startup |

### The RAM failure mode

If the Python dict TT is kept as-is and the table grows unbounded, the likely failure sequence is:

1. The ECS task's RSS exceeds its memory limit (or the instance's physical RAM).
2. The Linux OOM killer sends `SIGKILL` to the process — not `SIGTERM`, not a graceful shutdown signal.
3. `SIGKILL` cannot be caught. Python's `atexit` handlers, including `sync_queue.drain()`, **do not run**.
4. The TT is not saved to disk. The in-flight or queued S3 backup is abandoned. The last good S3 backup may be hundreds of moves stale.
5. ECS restarts the container. The process starts fresh, pulls the stale backup from S3 (or starts with an empty TT if no backup exists), and loses all TT progress since the last successful backup.
6. While the container is restarting, all `POST /move` requests to the engine return 503 `engine_unavailable` from the app layer.
7. If the table grows fast enough to hit the RAM limit on every restart, ECS enters a restart loop.

The fixed-size array eliminates this failure mode at the root: RAM is constant from startup, so the OOM kill never happens.

### Eviction policies: chess engines vs PokeChess

Because the fixed-size array has a finite number of slots, **hash collisions** require an eviction policy: when two different positions map to the same slot, one must give way to the other.

#### What chess engines do: simple replacement

In traditional chess engines (Stockfish, etc.), the TT is also a fixed-size hash array. The standard policy is **simple replacement**: when a collision occurs, the new entry unconditionally overwrites the existing one.

This is appropriate for chess because chess TTs are used for **within-search optimization**. When Stockfish starts a new search (a new move), it typically clears or ignores stale TT entries from the previous search — the statistics are rebuilt from scratch each time. Evicting an old entry has no lasting cost because the data was short-lived anyway.

#### Why simple replacement is wrong for PokeChess

PokeChess uses the TT very differently: it is an **inter-game learning mechanism**. Visit counts represent accumulated knowledge across many separate games, not just the current search. An entry with 1 million visits has been refined by rollouts across potentially thousands of game states; that entry's `wins/visits` ratio is a high-confidence estimate of the position's value.

Under simple replacement, a 1M-visit entry and a 1-visit entry are treated identically — both can be evicted by any colliding hash. A popular mid-game position that has been accurately evaluated over hundreds of games can be displaced by a novel position encountered once. When the popular position appears again in the next game, it re-enters the table with zero visits and the bot must re-explore it as if it has never seen it. All accumulated learning for that position is permanently lost.

At scale, simple replacement turns the TT into a sliding window that forgets high-value entries as fast as it learns them.

#### Visits-based replacement

A natural improvement: **only evict if the existing entry has fewer visits than the candidate**. This protects high-value entries — a 1M-visit entry will never be displaced by a 1-visit entry.

The problem is **table freezing**: once every slot has at least one visit, no new positions can ever enter the table. The bot cannot learn any new position it hasn't encountered before. This is particularly bad early in the table's life and after a version bump (when the TT is reset), when the bot needs to explore broadly.

#### Threshold-based replacement (chosen policy)

The chosen policy protects high-value entries while preserving the ability for new positions to enter:

```python
EVICT_THRESHOLD = 10

def update(self, h: int, win_delta: float) -> None:
    slot = h % self._size
    if self._hashes[slot] == h:
        # Same position — accumulate stats
        self._wins[slot] += win_delta
        self._visits[slot] += 1
    elif self._visits[slot] < EVICT_THRESHOLD:
        # Low-value or empty slot — replace
        self._hashes[slot] = h
        self._wins[slot] = win_delta
        self._visits[slot] = 1
    # else: existing entry has >= EVICT_THRESHOLD visits — protected, skip
```

**How it works:**

- Entries that have accumulated ≥ `EVICT_THRESHOLD` visits are **permanently protected** and will never be evicted.
- Entries below the threshold (including empty slots, which have 0 visits) can be displaced by new positions.
- As long as any below-threshold slot exists for a given hash modulo, a new position can enter the table.

**Tuning `EVICT_THRESHOLD`:**

A threshold of 10 means a position needs to be encountered at least 10 times across all games before it becomes protected. This is low enough that common positions earn protection quickly, but high enough that genuinely rare positions don't accumulate protected slots wastefully. The threshold can be exposed as an environment variable for tuning.

**The tradeoff:** once the table is full of protected entries (all slots have ≥ 10 visits), new positions are silently dropped. At that point the TT is functioning as a snapshot of the most-visited positions rather than a growing knowledge base. This is acceptable — a fully saturated table means the bot has extensive knowledge of the most common positions, which is exactly what we want. Newly encountered rare positions will benefit from rollout search even without TT priors.

### Summary of chosen design

| Property | Value |
|---|---|
| Storage type | Three `array.array` objects (hashes `'Q'`, wins `'f'`, visits `'I'`) |
| Slot count | Configurable; default 64M (1 GB RAM) |
| Memory | Fixed at startup — never grows |
| Lookup/insert | O(1) — `slot = hash % size` |
| Collision handling | Threshold-based replacement (`EVICT_THRESHOLD = 10`) |
| Save format | Sparse binary (only non-empty slots) — same 16-byte record format as current |

The external interface (`get()`, `update()`, `save()`, `load()`, `__len__()`) is unchanged. Only the internal storage and eviction logic are replaced.

---

## TT Versioning

The S3 key includes a version integer: `tt_v{version}.bin`, where `version` is read from the `POKECHESS_TT_VERSION` environment variable (default: `"1"`).

To invalidate existing stats after a rules change, set `POKECHESS_TT_VERSION` to a new integer in the task/container environment and redeploy. The old key is left in S3 (cheap storage, useful audit trail) and the bot starts fresh with an empty TT under the new key.

No metadata or header is stored inside the binary file itself — versioning lives entirely in the key name.

---

## Files

| File | Purpose |
|---|---|
| `bot/transposition.py` | In-memory TT; fixed-size `array.array` with threshold-based eviction |
| `bot/tt_store.py` | S3 client wrapper (`TTStore`) + background backup thread (`TTSyncQueue`) |
| `bot/server.py` | FastAPI server; wires TT startup, sync queue, and periodic enqueue |
| `tests/test_tt_store.py` | Mocked S3 tests for `TTStore` and `TTSyncQueue` |
| `tests/test_api.py` | Endpoint tests for `bot/server.py` |

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

2. S3 key tt_v{POKECHESS_TT_VERSION}.bin exists in POKECHESS_TT_BUCKET?
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

The app **does not** trigger TT backups and has no visibility into the TT. All persistence is the engine's internal concern. A `POST /backup` endpoint could be added for ops/admin use only (e.g. forcing a flush before a deploy) — it is not currently implemented and would not be called by the app.

---

## Configuration

### Environment variables

| Variable | Purpose |
|---|---|
| `POKECHESS_TT_LOCAL_PATH` | Path to the local TT binary file (default: `transposition_table.bin`) |
| `POKECHESS_TT_BUCKET` | S3 bucket name for TT backups. Omit to disable S3 entirely. |
| `POKECHESS_TT_VERSION` | TT version integer — used as part of the S3 key (`tt_v{N}.bin`). Bump to invalidate old stats after a rules change. |
| `POKECHESS_TT_SIZE` | Fixed slot count for the in-memory TT array. Default `1048576` (1M, 16 MB). Set to `67108864` (64M, ~1 GB) in production. |
| `AWS_DEFAULT_REGION` | Standard boto3 env var. Required when `POKECHESS_TT_BUCKET` is set. |
| `AWS_ACCESS_KEY_ID` | Explicit credential — **local dev only** (see IAM note below). |
| `AWS_SECRET_ACCESS_KEY` | Explicit credential — **local dev only** (see IAM note below). |

### IAM credentials — chosen approach: ECS task role (Option B)

**Production uses an ECS task role. `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are never set in the production engine task.**

How it works: an IAM role is attached to the `pokechess-engine` ECS task definition. The role's policy grants `s3:GetObject`, `s3:PutObject`, and `s3:HeadObject` on the TT bucket. boto3 resolves credentials automatically via the default credential chain — on ECS on EC2 this is the EC2 instance metadata service (IMDSv2); on ECS Fargate this is the ECS task metadata endpoint. Either way, no secrets to manage, no rotation needed, and no credentials in environment variables or config files.

Steps to wire up at deploy time:
1. Create an IAM role (e.g. `pokechess-engine-task-role`) with a trust policy allowing `ecs-tasks.amazonaws.com`.
2. Attach an inline or managed policy granting the three S3 actions above on `arn:aws:s3:::<bucket>` and `arn:aws:s3:::<bucket>/*`.
3. Set `taskRoleArn` to this role's ARN in the `pokechess-engine` ECS task definition.
4. Set `POKECHESS_TT_BUCKET` and `AWS_DEFAULT_REGION` as task environment variables; leave `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` unset.

**Local development:** If you want to exercise S3 backup locally, set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or configure an `~/.aws/credentials` profile). Omitting `POKECHESS_TT_BUCKET` entirely disables S3 and is the simplest local setup.

---

## Verification

| Test | Method | Status |
|---|---|---|
| Local-first startup | Local file present → S3 never contacted | Implemented (`tests/test_tt_store.py`) |
| S3 fallback startup | No local file, S3 key exists → downloaded and loaded correctly | Implemented |
| Fresh start | No local file, S3 key absent → `global_tt` starts empty; no error | Implemented |
| S3 error fallback | S3 download raises → `global_tt` starts empty; engine still serves requests | Implemented (`tests/test_api.py`) |
| Backup round-trip | Save TT → upload → download → load → stats match original | Implemented |
| Queue deduplication | Enqueueing twice while worker is busy results in one upload, not two | Implemented |
| Drain on shutdown | `drain()` blocks until in-flight backup completes | Implemented |
| Version isolation | Changing `POKECHESS_TT_VERSION` targets a different S3 key; old stats not loaded | Implemented |
| Array round-trip | Fixed-size array TT: save (sparse) → load → stats match for populated entries | Implemented (`tests/test_mcts.py`) |
| Threshold protection | Entry with ≥ `EVICT_THRESHOLD` visits is not displaced by a colliding hash | Implemented |
| Below-threshold eviction | Entry with < `EVICT_THRESHOLD` visits is displaced; new entry is stored correctly | Implemented |
