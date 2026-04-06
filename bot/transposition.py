"""
Persistent transposition table for inter-game learning.

Maps Zobrist hash → (wins, visits) and survives across games.
On tree node creation, existing stats warm-start the node rather
than starting from 0/0, giving the bot informed priors from
positions seen in previous games.

wins always reflects the mover's perspective: wins for the player
who made the move to reach the hashed position.

Use save(path) / load(path) to persist across process restarts.
The file format is a binary stream of (hash, wins, visits) records:
  8 bytes  — uint64 Zobrist hash (little-endian)
  4 bytes  — float32 cumulative wins (little-endian)
  4 bytes  — uint32 visit count (little-endian)
= 16 bytes per record
"""

from __future__ import annotations

import os
import struct


_RECORD_FMT  = '<QfI'   # uint64 hash, float32 wins, uint32 visits  → 16 bytes
_RECORD_SIZE = struct.calcsize(_RECORD_FMT)  # 16


class TranspositionTable:
    """Global stats table. Persists across MCTS instances and games."""

    def __init__(self) -> None:
        self._data: dict[int, tuple[float, int]] = {}

    def get(self, h: int) -> tuple[float, int]:
        """Return (wins, visits) for hash h, or (0.0, 0) if unseen."""
        return self._data.get(h, (0.0, 0))

    def update(self, h: int, win_delta: float) -> None:
        """Add win_delta wins and 1 visit to the entry for hash h."""
        wins, visits = self._data.get(h, (0.0, 0))
        self._data[h] = (wins + win_delta, visits + 1)

    def __len__(self) -> int:
        return len(self._data)

    def save(self, path: str) -> None:
        """Write all entries to a binary file at path (atomic via temp file)."""
        tmp = path + '.tmp'
        with open(tmp, 'wb') as f:
            for h, (wins, visits) in self._data.items():
                f.write(struct.pack(_RECORD_FMT, h, wins, visits))
        os.replace(tmp, path)

    def load(self, path: str) -> None:
        """Load entries from a binary file written by save(). Merges into existing data."""
        if not os.path.exists(path):
            return
        with open(path, 'rb') as f:
            raw = f.read()
        n = len(raw) // _RECORD_SIZE
        offset = 0
        for _ in range(n):
            h, wins, visits = struct.unpack_from(_RECORD_FMT, raw, offset)
            offset += _RECORD_SIZE
            existing_wins, existing_visits = self._data.get(h, (0.0, 0))
            self._data[h] = (existing_wins + wins, existing_visits + visits)
