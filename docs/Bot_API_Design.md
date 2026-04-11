# Bot API Design

**Status:** Approved, pre-implementation  
**Authors:** nherringer  
**Audience:** ML bot team + frontend/async team

---

## Overview

This document covers the design of the HTTP bot API and the serialization layer (PokeChess-FEN and PokeChess-PGN) that underlies it. The API allows the app layer to query the ML bot for a move given the current game state and a set of `persona_params`.

The API is **stateless** — it holds no per-game session state between requests. Each request is self-contained: the caller provides the full game state and the bot responds with a move. No pondering is implemented for the MVP.

For background on why the Zobrist hash is insufficient for state serialization, and the full rationale for the FEN/PGN formats, see `docs/PokeChess_Notation_Design.md`.

---

## Implementation Order

1. **FEN serialization** (`engine/state.py`, `engine/moves.py`) + round-trip tests — prerequisite for everything
2. **Bot API** (`bot/server.py`) + endpoint tests
3. **PGN notation** (`engine/notation.py`) — after API is stable

---

## Phase 1 — FEN Serialization

### Files modified

| File | Change |
|---|---|
| `engine/state.py` | Add `GameState.from_dict()` (see note below) |
| `engine/moves.py` | Add `Move.to_dict()` |
| `tests/test_serialization.py` | New — round-trip tests |

> **Note — two serialization layers exist.** The app backend (`init/app-backend`) already implements its own state serialization in `app/game_logic/serialization.py` as standalone functions (`state_to_dict` / `state_from_dict`). That format includes a piece-level `"id"` field (UUID) used by the app's roster and move-history system. The engine container never has access to UUIDs — they are app-only state. What the engine needs is:
>
> - `GameState.from_dict(d)` in `engine/state.py`: deserializes the wire dict the app sends. It must silently ignore any extra fields (specifically `"id"` on piece entries) that the app adds. The engine does **not** need `GameState.to_dict()` — the engine only receives state, it never serializes it back.
> - `Move.to_dict()` in `engine/moves.py`: serializes the chosen move for the HTTP response. Returns a flat dict (see response format in Phase 2).
>
> `GameState.from_dict()` is essentially the same as `app/game_logic/serialization.py`'s `state_from_dict()` minus the UUID bookkeeping.

### `GameState.from_dict(d)`

- `board` entries are piece dicts with `row`/`col` encoding position; unknown fields (e.g. `"id"`) are ignored
- `active_player` → `Team[d["active_player"]]`
- `pending_foresight`, `has_traded`, `foresight_used_last_turn` → same structure as the app format

### `Move.to_dict()`

- `action_type` → `ActionType.name` string (e.g. `"MOVE"`, `"ATTACK"`)
- All optional fields (`secondary_row`, `secondary_col`, `move_slot`) included as `null` when absent
- Returns a **flat** dict (not nested under a `"move"` key — see Phase 2 response format)

### Example FEN output (abbreviated)

```json
{
  "active_player": "RED",
  "turn_number": 14,
  "has_traded": {"RED": false, "BLUE": false},
  "foresight_used_last_turn": {"RED": false, "BLUE": true},
  "pending_foresight": {
    "RED": null,
    "BLUE": {"target_row": 4, "target_col": 3, "damage": 120, "resolves_on_turn": 15}
  },
  "board": [
    {"piece_type": "SQUIRTLE", "team": "RED", "row": 3, "col": 2,
     "current_hp": 160, "held_item": "WATERSTONE", "stored_piece": null},
    {"piece_type": "SAFETYBALL", "team": "BLUE", "row": 5, "col": 4,
     "current_hp": 0, "held_item": "NONE",
     "stored_piece": {"piece_type": "EEVEE", "team": "BLUE",
                      "row": 5, "col": 4, "current_hp": 80,
                      "held_item": "THUNDERSTONE", "stored_piece": null}}
  ]
}
```

### Example Move dict output

```json
{
  "piece_row": 1,
  "piece_col": 4,
  "action_type": "MOVE",
  "target_row": 3,
  "target_col": 4,
  "secondary_row": null,
  "secondary_col": null,
  "move_slot": null
}
```

### Verification

| Test | Method |
|---|---|
| FEN round-trip | Serialize a mid-game state via `app/game_logic/serialization.py`'s `state_to_dict()`, then round-trip through `GameState.from_dict()` in the engine — board, HP, foresight, and flags must match |
| UUID passthrough | Piece dicts with `"id"` fields deserialize without error; `"id"` is ignored by the engine |
| Move serialization | `Move.to_dict()` for all `ActionType` values including QUICK_ATTACK; optional fields serialize as `null` |

---

## Phase 2 — Bot API

### Stack

- **Framework:** FastAPI
- **Server:** Uvicorn
- **New dependencies:** `fastapi`, `uvicorn`, `boto3`

### Files created

| File | Purpose |
|---|---|
| `bot/server.py` | FastAPI app, lifespan, single endpoint |
| `tests/test_api.py` | Endpoint tests |

### Global process state (created at startup)

```
global_tt: TranspositionTable   # single local TT, shared across all requests
request_count: int              # total requests served; triggers TT backup at multiples of 50
tt_sync_queue: TTSyncQueue      # see docs/Transposition_Table_Sync.md
```

No per-request or per-game state is retained between calls. The global TT accumulates statistics across all requests for the lifetime of the process.

> **TT memory budget:** The TT grows to millions of entries quickly (empirically ~5M after the first 5–10 games). The in-memory representation is being refactored from a Python dict (~156 bytes/entry) to a fixed-size `array.array` (16 bytes/entry, pre-allocated at startup). See `docs/Transposition_Table_Sync.md` — "TT Implementation Design" — for the full rationale, failure mode, and eviction policy.

### Playstyle parameters

Each request includes a `persona_params` object that controls MCTS behavior for that move. Known keys map directly to `MCTS` constructor parameters; unknown keys are forwarded and ignored by the engine so future tuning params require no app-side code change.

| Parameter | Type | Description |
|---|---|---|
| `time_budget` | float (seconds) | How long MCTS searches before selecting a move. Controls difficulty. |
| `exploration_c` | float | UCB1 exploration constant. Higher = more exploration. Default: `sqrt(2)`. |

Additional parameters can be added to `persona_params` without a code change on the app side.

### Endpoint

#### `POST /move`

Requests the bot's move for the given game state.

```
Request body:
{
  "state":         { <FEN dict> },
  "persona_params": {
    "time_budget":   1.0,
    "exploration_c": 1.414
  }
}

Response 200 — flat Move dict (not nested under a "move" key):
{
  "piece_row": 1,
  "piece_col": 4,
  "action_type": "MOVE",
  "target_row": 3,
  "target_col": 4,
  "secondary_row": null,
  "secondary_col": null,
  "move_slot": null
}
```

Processing steps:
1. Deserialize `state` via `GameState.from_dict()` (ignores `"id"` fields on piece entries)
2. Extract `persona_params["time_budget"]` (and optionally `exploration_c`) to construct `MCTS(..., transposition=global_tt)`
3. Call `mcts.select_move(state)` → `Move`
4. Increment `request_count`; if `request_count % 50 == 0`: enqueue TT backup
5. Return `chosen_move.to_dict()` as a flat JSON object

### Startup lifespan (`bot/server.py` lifespan event)

On startup:
1. Check for local TT file on disk; if found, load into `global_tt`
2. If no local TT: attempt to download from S3 → load into `global_tt`
3. If S3 key also does not exist: start with an empty `global_tt`
4. Start background TT sync thread

The app does **not** trigger TT backups — persistence is entirely the engine's responsibility. `Dockerfile.engine` mentions a `POST /backup` endpoint; if exposed, it is for ops/admin use only and is not called by the app. The `TTSyncQueue` handles periodic backups automatically.

See `docs/Transposition_Table_Sync.md` for the full startup and sync design.

---

## Phase 3 — PGN Notation

Deferred until Phase 2 is stable. See `docs/PokeChess_Notation_Design.md` for full spec.

**Files to create:**
- `engine/notation.py` — `move_to_str()`, `str_to_move()`, `GameRecord` class
- `tests/test_notation.py` — round-trip and stochastic-replay tests
