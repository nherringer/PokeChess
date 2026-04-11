"""
Persistent transposition table for inter-game learning.

Maps Zobrist hash → (wins, visits) and survives across games.
On tree node creation, existing stats warm-start the node rather
than starting from 0/0, giving the bot informed priors from
positions seen in previous games.

wins always reflects the mover's perspective: wins for the player
who made the move to reach the hashed position.

Use save(path) / load(path) to persist across process restarts.
The file format is a sparse binary stream — only occupied slots are
written.  Each record is:
  8 bytes  — uint64 Zobrist hash (little-endian)
  4 bytes  — float32 cumulative wins (little-endian)
  4 bytes  — uint32 visit count (little-endian)
= 16 bytes per record

Implementation: three parallel array.array objects (hashes 'Q', wins 'f',
visits 'I') pre-allocated at construction.  This uses exactly 16 bytes
per slot regardless of occupancy — constant RAM from startup, versus
~156 bytes per entry for a Python dict.

Collision policy: threshold-based replacement.  A slot whose visit count
has reached EVICT_THRESHOLD is permanently protected; only empty or
below-threshold slots can be displaced by a colliding hash.  This
prevents high-value inter-game learning entries from being evicted while
still allowing new positions to enter the table.

Default slot count (DEFAULT_TT_SIZE = 1M) is sized for safe use in tests
and dev.  Set POKECHESS_TT_SIZE to a larger value in server.py for
production (e.g. 67108864 = 64M slots = 1 GB RAM).
"""

from __future__ import annotations

import array
import os
import struct


_RECORD_FMT  = '<QfI'   # uint64 hash, float32 wins, uint32 visits  → 16 bytes
_RECORD_SIZE = struct.calcsize(_RECORD_FMT)  # 16

# Entries whose visit count reaches this threshold are permanently protected
# from eviction.  New colliding hashes cannot displace them.
EVICT_THRESHOLD: int = 10

# Default slot count — keeps memory modest for tests and dev.
# Production should pass an explicit size (e.g. 64_000_000 = ~1 GB).
DEFAULT_TT_SIZE: int = 1 << 20  # 1,048,576 slots = 16 MB


class TranspositionTable:
    """
    Fixed-size hash array mapping Zobrist hashes to (wins, visits).

    Three parallel array.array objects provide 16 bytes/slot; memory is
    allocated once at construction and never grows.  A Python dict would
    require ~156 bytes per entry due to CPython object overhead, which
    becomes several GB after tens of millions of unique positions.

    Lookup: slot = hash % size   O(1), no dynamic allocation.
    """

    def __init__(self, size: int = DEFAULT_TT_SIZE) -> None:
        self._size = size
        # Zero-initialise via bytes() — fast C-level memset, no Python loop.
        self._hashes = array.array('Q', bytes(size * 8))   # uint64, sentinel 0 = empty
        self._wins   = array.array('f', bytes(size * 4))   # float32
        self._visits = array.array('I', bytes(size * 4))   # uint32
        self._count  = 0  # number of occupied slots (visits > 0)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, h: int) -> tuple[float, int]:
        """Return (wins, visits) for hash h, or (0.0, 0) if unseen / evicted."""
        slot = h % self._size
        if self._hashes[slot] == h and self._visits[slot] > 0:
            return float(self._wins[slot]), int(self._visits[slot])
        return (0.0, 0)

    def update(self, h: int, win_delta: float) -> None:
        """
        Add win_delta wins and 1 visit to the entry for hash h.

        Collision policy:
          - Same hash in slot → accumulate (no eviction).
          - Different hash, slot visits < EVICT_THRESHOLD → evict and replace.
          - Different hash, slot visits >= EVICT_THRESHOLD → protected, skip.
        """
        slot = h % self._size
        if self._hashes[slot] == h:
            # Same position — accumulate stats.
            # Edge case: slot.visits may be 0 if hash collides with the
            # all-zero sentinel (Zobrist hash = 0).  Increment count here.
            if self._visits[slot] == 0:
                self._count += 1
            self._wins[slot] += win_delta
            self._visits[slot] += 1
        elif self._visits[slot] < EVICT_THRESHOLD:
            # Low-value or empty slot — replace.
            if self._visits[slot] == 0:
                self._count += 1
            self._hashes[slot] = h
            self._wins[slot] = win_delta
            self._visits[slot] = 1
        # else: >= EVICT_THRESHOLD visits on a different hash — protected, skip.

    def __len__(self) -> int:
        return self._count

    def save(self, path: str) -> None:
        """
        Write all occupied slots to a binary file at path (atomic via temp file).

        Only non-empty slots are written (sparse format) so file size scales
        with the number of positions encountered, not the total slot count.
        """
        tmp = path + '.tmp'
        pack = struct.pack
        fmt = _RECORD_FMT
        hashes = self._hashes
        wins   = self._wins
        visits = self._visits
        with open(tmp, 'wb') as f:
            write = f.write
            for slot in range(self._size):
                v = visits[slot]
                if v:
                    write(pack(fmt, hashes[slot], wins[slot], v))
        os.replace(tmp, path)

    def load(self, path: str) -> None:
        """
        Load entries from a binary file written by save().  Merges into
        existing data using the same threshold-based replacement policy:

          - Matching hash in slot → merge wins and visits (accumulate).
          - Empty or below-threshold slot → write directly.
          - Protected slot with a different hash → skip.
        """
        if not os.path.exists(path):
            return
        with open(path, 'rb') as f:
            raw = f.read()
        n = len(raw) // _RECORD_SIZE
        offset = 0
        for _ in range(n):
            h, wins, visits = struct.unpack_from(_RECORD_FMT, raw, offset)
            offset += _RECORD_SIZE
            slot = h % self._size
            if self._hashes[slot] == h and self._visits[slot] > 0:
                # Same position — merge accumulated stats.
                self._wins[slot]   += wins
                self._visits[slot] += visits
            elif self._visits[slot] < EVICT_THRESHOLD:
                # Empty or evictable — write directly.
                if self._visits[slot] == 0:
                    self._count += 1
                self._hashes[slot] = h
                self._wins[slot]   = wins
                self._visits[slot] = visits
            # else: protected slot with different hash — skip.
