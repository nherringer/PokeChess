# PokéChess — Data Model Reference

**Status:** Design complete, ready for implementation  
**Database:** PostgreSQL on AWS RDS (single database, no DynamoDB)  
**Backend:** FastAPI (app server) + separate engine container (MCTS bot)  
**Last updated:** April 2026

---

## Table of Contents

1. [Architecture overview](#architecture-overview)
2. [Schema — all tables](#schema)
3. [Constraints & indexes](#constraints--indexes)
4. [JSON column shapes](#json-column-shapes)
5. [Key design decisions](#key-design-decisions)
6. [Move lifecycle flow](#move-lifecycle-flow)
7. [Future extensibility notes](#future-extensibility-notes)

---

## Architecture Overview

The app server (FastAPI) is the only process that touches the database. The engine container is internal-only — the app server calls it via HTTP (PvB only), passes the current game state, and gets back the bot's chosen move. The app applies all moves (human and bot) using the shared `engine/` library directly. The frontend never talks to the engine directly.

```
React frontend
    ↓  REST (polling)
FastAPI app server  ←→  PostgreSQL RDS
    ↓  internal HTTP
Engine container (MCTS bot)
```

**Polling, not WebSockets.** Games are async; a 1–3 second delay is acceptable. The frontend polls `GET /games/{id}` on the game view. SSE is a future upgrade path if needed.

**One database.** At 5–20 users, DynamoDB adds operational complexity with no benefit. PostgreSQL JSONB handles semi-structured game state natively. JSONB is fully supported on AWS RDS for PostgreSQL (all current versions).

---

## Schema

### `users`

Core identity table. Minimal — auth fields only. No settings here.

```sql
CREATE TABLE users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR     UNIQUE NOT NULL,
    email         VARCHAR     UNIQUE NOT NULL,
    password_hash VARCHAR     NOT NULL,
    created_at    TIMESTAMP   NOT NULL DEFAULT now()
);
```

---

### `user_settings`

1:1 with users. Known, stable settings get explicit columns. `extra_settings` is a JSONB catch-all for anything that hasn't stabilized yet. When a setting in `extra_settings` proves permanent, promote it to a real column via migration.

```sql
CREATE TABLE user_settings (
    user_id        UUID        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    board_theme    VARCHAR     NOT NULL DEFAULT 'classic',
    extra_settings JSONB       NOT NULL DEFAULT '{}',
    updated_at     TIMESTAMP
);
```

**Example `extra_settings` value:**
```json
{
  "show_move_hints": true,
  "sound_enabled": false
}
```

---

### `friendships`

`user_a_id` always holds the lexicographically lesser UUID so each pair has exactly one row. `initiator_id` records who sent the request — used to enforce that only the recipient can accept or reject.

```sql
CREATE TABLE friendships (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id     UUID        NOT NULL REFERENCES users(id),
    user_b_id     UUID        NOT NULL REFERENCES users(id),
    initiator_id  UUID        NOT NULL REFERENCES users(id),
    status        VARCHAR     NOT NULL,   -- 'pending' | 'accepted' | 'rejected'
    created_at    TIMESTAMP   NOT NULL DEFAULT now(),

    CONSTRAINT friendships_order   CHECK (user_a_id::text < user_b_id::text),
    CONSTRAINT friendships_status  CHECK (status IN ('pending', 'accepted', 'rejected')),
    UNIQUE (user_a_id, user_b_id)
);

CREATE INDEX idx_friendships_a ON friendships (user_a_id);
CREATE INDEX idx_friendships_b ON friendships (user_b_id);
```

---

### `bots`

One row per bot personality. v1 has a single row. Adding a new difficulty = new row, no schema change. `params` is JSONB because bot tuning values will evolve as the engine is tuned — the shape is genuinely fluid. The app server reads the whole `params` blob and passes it directly to the engine.

```sql
CREATE TABLE bots (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR     NOT NULL,   -- e.g. 'Easy Bot', 'Standard Bot'
    params      JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMP   NOT NULL DEFAULT now()
);
```

**Example `params` value** (MCTS levers from the engine):
```json
{
  "time_budget": 1.0,
  "iteration_budget": null,
  "rollout_policy_weights": {
    "capture": 1.5,
    "advance": 1.0,
    "defend_king": 2.0,
    "random": 0.3
  },
  "playstyle_config": {
    "aggression": 0.7,
    "king_safety": 0.8,
    "piece_preservation": 0.5
  },
  "type_affinity_scorer": {
    "prefer_type_effective": true,
    "affinity_bonus": 0.2
  },
  "use_cpp_rollout": false
}
```

**Parameter reference** (from engine source):

| Parameter | Location in engine | Effect |
|---|---|---|
| `time_budget` | `MCTS.__init__` | Controls search depth → overall strength |
| `iteration_budget` | `select_move` loop | Deterministic alternative to time budget |
| `rollout_policy_weights` | `_rollout` | Shapes playstyle (aggressive, defensive, etc.) |
| `playstyle_config` | `PlaystyleConfig` dataclass | Encapsulates per-personality behaviour |
| `type_affinity_scorer` | `custom_scorer` | Thematic piece-type preferences |
| `use_cpp_rollout` | `_iterate_cpp_batch` | Bypasses Python policy for performance |

> **Note:** `time_budget` and `iteration_budget` are mutually exclusive. Set one, leave the other `null`.

---

### `game_invites`

Created when a player challenges a friend. The game row is created in `status = 'pending'` at the same time. Game transitions to `'active'` when the invite is accepted.

```sql
CREATE TABLE game_invites (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_id  UUID        NOT NULL REFERENCES users(id),
    invitee_id  UUID        NOT NULL REFERENCES users(id),
    status      VARCHAR     NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMP   NOT NULL DEFAULT now(),

    CONSTRAINT invite_status CHECK (status IN ('pending', 'accepted', 'rejected', 'expired'))
);
```

---

### `games`

One row per game. Updated on every move. The two JSONB columns (`state`, `move_history`) handle semi-structured engine data. All fields that are frequently queried (status, whose_turn, winner) are real columns — never buried in JSONB.

```sql
CREATE TABLE games (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Players (both nullable: null = that side is occupied by the bot)
    red_player_id   UUID        REFERENCES users(id),
    blue_player_id  UUID        REFERENCES users(id),

    -- Bot fields (all null for PvP)
    is_bot_game     BOOLEAN     NOT NULL DEFAULT false,
    bot_id          UUID        REFERENCES bots(id),
    bot_side        VARCHAR,    -- 'red' | 'blue' — stored for convenience, also implicit from null player slot

    -- Invite (null for PvB)
    invite_id       UUID        REFERENCES game_invites(id),

    -- Game state (real columns for queryability)
    status          VARCHAR     NOT NULL DEFAULT 'pending',  -- 'pending' | 'active' | 'complete'
    whose_turn      VARCHAR,                                  -- 'red' | 'blue'
    turn_number     INT         NOT NULL DEFAULT 0,

    -- Game state (JSONB — engine data)
    state           JSONB,      -- Full engine GameState snapshot, overwritten each move (~5–6 KB)
    move_history    JSONB       NOT NULL DEFAULT '[]',  -- Append-only array (~200 bytes/entry)

    -- Outcome
    winner          VARCHAR,    -- 'red' | 'blue' | 'draw'
    end_reason      VARCHAR,    -- 'king_eliminated' | 'resign' | 'timeout' | 'draw'

    created_at      TIMESTAMP   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP   NOT NULL DEFAULT now(),

    -- Integrity constraints
    CONSTRAINT game_status    CHECK (status IN ('pending', 'active', 'complete')),
    CONSTRAINT game_turn      CHECK (whose_turn IN ('red', 'blue')),
    CONSTRAINT game_winner    CHECK (winner IN ('red', 'blue', 'draw')),
    CONSTRAINT game_end       CHECK (end_reason IN ('king_eliminated', 'resign', 'timeout', 'draw')),
    CONSTRAINT bot_side_valid CHECK (bot_side IS NULL OR bot_side IN ('red', 'blue')),

    -- Bot/player consistency
    -- PvP: both players set, no bot fields
    -- PvB: exactly one player set, bot fields set
    CONSTRAINT bot_consistency CHECK (
        (is_bot_game = false
            AND bot_id IS NULL AND bot_side IS NULL
            AND red_player_id IS NOT NULL AND blue_player_id IS NOT NULL)
        OR
        (is_bot_game = true
            AND bot_id IS NOT NULL AND bot_side IS NOT NULL
            AND num_nonnulls(red_player_id, blue_player_id) = 1)
    )
);
```

---

### `pokemon_pieces`

Persistent Pokémon owned by a player. Accumulates XP and evolves across games. **Named pieces only** — Stealballs and Safetyballs are ephemeral game units and are not tracked here.

> **Critical:** `pokemon_pieces.id` is the same UUID used as `piece_id` inside `state.pieces[]` and `move_history` entries. This is the link that makes XP attribution work — no translation layer needed.

```sql
CREATE TABLE pokemon_pieces (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id         UUID        NOT NULL REFERENCES users(id),
    role             VARCHAR     NOT NULL,   -- 'king' | 'queen' | 'rook' | 'bishop' | 'knight'
    species          VARCHAR     NOT NULL,   -- current species, mutable on evolution
                                             -- e.g. 'pikachu' → 'raichu', 'eevee' → 'espeon'
    xp               INT         NOT NULL DEFAULT 0,
    evolution_stage  INT         NOT NULL DEFAULT 0,
    created_at       TIMESTAMP   NOT NULL DEFAULT now(),

    CONSTRAINT piece_role CHECK (role IN ('king', 'queen', 'rook', 'bishop', 'knight'))
);
```

**Each user gets 5 persistent Pokémon at account creation:**

| Role | Red team (Pikachu side) | Blue team (Eevee side) |
|---|---|---|
| King | Pikachu (→ Raichu) | Eevee (→ Vaporeon/Flareon/Leafeon/Jolteon/Espeon) |
| Queen | Mew | Mew |
| Rook | Squirtle | Squirtle |
| Knight | Charmander | Charmander |
| Bishop | Bulbasaur | Bulbasaur |

---

### `game_pokemon_map`

Join table linking named Pokémon pieces to a specific game. Written at game creation. XP columns written at game end by business logic.

Separates **earned XP** (raw activity, always recorded) from **applied XP** (subject to business rules — currently wins only). This means the XP rule can change without touching historical data.

```sql
CREATE TABLE game_pokemon_map (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id           UUID        NOT NULL REFERENCES games(id),
    pokemon_piece_id  UUID        NOT NULL REFERENCES pokemon_pieces(id),

    -- XP tracking
    xp_earned         INT         NOT NULL DEFAULT 0,   -- raw XP regardless of outcome
    xp_applied        INT         NOT NULL DEFAULT 0,   -- what actually got added to pokemon_pieces.xp
    xp_applied_at     TIMESTAMP,                         -- null = not yet processed
    xp_skip_reason    VARCHAR,                           -- 'loss' | 'draw' | 'resign' | null (applied)

    UNIQUE (game_id, pokemon_piece_id)
);

-- Fast lookup of unprocessed XP rows at game end
CREATE INDEX idx_gpm_unapplied ON game_pokemon_map (game_id)
WHERE xp_applied_at IS NULL;
```

**XP rollup query (run at game end):**
```sql
UPDATE pokemon_pieces p
SET
    xp = xp + gpm.xp_applied,
    evolution_stage = CASE
        WHEN (xp + gpm.xp_applied) >= 100 THEN 2   -- thresholds TBD
        WHEN (xp + gpm.xp_applied) >= 30  THEN 1
        ELSE evolution_stage
    END
FROM game_pokemon_map gpm
WHERE gpm.game_id = $1
  AND gpm.pokemon_piece_id = p.id
  AND gpm.xp_applied_at IS NULL;
```

---

## Constraints & Indexes

### Friendships

```sql
-- No duplicate pairs, enforced by ordering convention
UNIQUE (user_a_id, user_b_id)
CHECK (user_a_id::text < user_b_id::text)

-- Fast friend-list lookups
CREATE INDEX idx_friendships_a ON friendships (user_a_id);
CREATE INDEX idx_friendships_b ON friendships (user_b_id);
```

### Games — uniqueness (one active game per pair)

```sql
-- One active PvP game per player pair (order-independent)
CREATE UNIQUE INDEX one_active_pvp
ON games (
    LEAST(red_player_id::text, blue_player_id::text),
    GREATEST(red_player_id::text, blue_player_id::text)
)
WHERE status = 'active' AND is_bot_game = false;

-- One active PvB game per human player per bot
CREATE UNIQUE INDEX one_active_pvb
ON games (COALESCE(red_player_id, blue_player_id), bot_id)
WHERE status = 'active' AND is_bot_game = true;
```

> `COALESCE(red_player_id, blue_player_id)` always resolves to the human player's ID in a bot game since exactly one is non-null. `bot_side` is not needed in the index — the uniqueness constraint is about the player+bot pair, not which color they play.

### Games — query indexes

```sql
-- Lobby: active games for a user
CREATE INDEX idx_games_red_active  ON games (red_player_id)  WHERE status = 'active';
CREATE INDEX idx_games_blue_active ON games (blue_player_id) WHERE status = 'active';

-- History: completed games for a user
CREATE INDEX idx_games_red_done    ON games (red_player_id)  WHERE status = 'complete';
CREATE INDEX idx_games_blue_done   ON games (blue_player_id) WHERE status = 'complete';
```

---

## JSON Column Shapes

### `games.state` (JSONB)

Overwritten on every move. This is the complete snapshot needed to resume the game cold. It is the direct JSON output of `GameState.to_dict()` and is consumed by `GameState.from_dict()` — both defined in `engine/state.py`. The app deserializes this to a `GameState` object in order to call engine functions (move validation, move application, terminal detection).

**Size:** ~4–5 KB at full board (on-board pieces only, no captured-piece tracking). Stored inline by Postgres (below TOAST threshold).

```json
{
  "active_player": "RED",
  "turn_number": 6,
  "has_traded": {"RED": false, "BLUE": false},
  "foresight_used_last_turn": {"RED": false, "BLUE": false},
  "pending_foresight": {
    "RED": null,
    "BLUE": {
      "target_row": 4,
      "target_col": 3,
      "damage": 120,
      "resolves_on_turn": 8
    }
  },
  "board": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "piece_type": "RAICHU",
      "team": "RED",
      "row": 0,
      "col": 4,
      "current_hp": 220,
      "held_item": "NONE",
      "stored_piece": null
    },
    {
      "id": null,
      "piece_type": "SAFETYBALL",
      "team": "RED",
      "row": 3,
      "col": 4,
      "current_hp": 0,
      "held_item": "NONE",
      "stored_piece": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "piece_type": "CHARMANDER",
        "team": "RED",
        "row": 3,
        "col": 4,
        "current_hp": 160,
        "held_item": "FIRESTONE",
        "stored_piece": null
      }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "piece_type": "SQUIRTLE",
      "team": "BLUE",
      "row": 5,
      "col": 2,
      "current_hp": 200,
      "held_item": "WATERSTONE",
      "stored_piece": null
    }
  ]
}
```

**State field reference:**

| Field | Type | Notes |
|---|---|---|
| `active_player` | string | `"RED"` or `"BLUE"` — matches `Team` enum name |
| `turn_number` | int | Increments each half-move |
| `has_traded` | `{"RED": bool, "BLUE": bool}` | Free-action trade gate; required for cold resume |
| `foresight_used_last_turn` | `{"RED": bool, "BLUE": bool}` | Prevents consecutive Foresight; required for cold resume |
| `pending_foresight` | `{"RED": effect\|null, "BLUE": effect\|null}` | At most one queued Foresight per team |
| `foresight.target_row/col` | int (0–7) | Target square; row 0 = Red's back rank |
| `foresight.damage` | int | Pre-calculated at cast time (120 for Mew and Espeon) |
| `foresight.resolves_on_turn` | int | Absolute turn number when damage lands |
| `board[]` | array | On-board pieces only; captured pieces are removed and not tracked |
| `piece.id` | UUID string or null | Same as `pokemon_pieces.id` for named pieces; null for Pokéballs/Safetyballs (ephemeral) |
| `piece.piece_type` | string | Engine `PieceType` enum name (e.g. `"SQUIRTLE"`, `"RAICHU"`, `"SAFETYBALL"`) |
| `piece.team` | string | `"RED"` or `"BLUE"` |
| `piece.row` / `piece.col` | int (0–7) | Board position using engine-native coordinates |
| `piece.current_hp` | int | 0 for Safetyballs/Pokéballs (no HP stat) |
| `piece.held_item` | string | Engine `Item` enum name (e.g. `"WATERSTONE"`, `"NONE"`) |
| `piece.stored_piece` | piece object or null | Inline nested piece stored inside a Safetyball; null otherwise |

---

### `games.move_history` (JSONB)

Append-only array. One entry per action (plus one auto-injected entry when Foresight resolves). RNG outcomes (Pokéball rolls) are recorded here, not in `state`. Coordinates use engine-native row/col integers throughout.

**Size estimates:**
- ~250 bytes per entry (average across action types)
- 100 moves → ~25 KB raw, ~12 KB compressed
- 500 moves → ~125 KB raw, ~60 KB compressed (likely upper bound)

Postgres TOAST handles values above ~8 KB transparently — no configuration needed, no query changes required.

```json
[
  {
    "turn": 1,
    "player": "RED",
    "action_type": "move",
    "piece_id": "550e8400-e29b-41d4-a716-446655440003",
    "from_row": 1, "from_col": 5,
    "to_row": 3, "to_col": 5,
    "result": {}
  },
  {
    "turn": 2,
    "player": "BLUE",
    "action_type": "attack",
    "piece_id": "550e8400-e29b-41d4-a716-446655440004",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440003",
    "from_row": 6, "from_col": 3,
    "to_row": 3, "to_col": 5,
    "result": {
      "damage": 40,
      "type_multiplier": 2.0,
      "target_hp_before": 200,
      "target_hp_after": 160,
      "captured": false
    }
  },
  {
    "turn": 3,
    "player": "RED",
    "action_type": "pokeball_attack",
    "piece_id": null,
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440004",
    "from_row": 1, "from_col": 0,
    "to_row": 2, "to_col": 1,
    "result": {
      "rng_roll": 0.73,
      "captured": false,
      "pokeball_spent": true
    }
  },
  {
    "turn": 4,
    "player": "BLUE",
    "action_type": "move",
    "piece_id": null,
    "from_row": 6, "from_col": 2,
    "to_row": 4, "to_col": 2,
    "result": {
      "stored": true,
      "stored_piece_id": "550e8400-e29b-41d4-a716-446655440003",
      "stored_hp": 160,
      "stored_max_hp": 200
    }
  },
  {
    "turn": 5,
    "player": "RED",
    "action_type": "quick_attack",
    "piece_id": "550e8400-e29b-41d4-a716-446655440005",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440006",
    "from_row": 7, "from_col": 4,
    "attack_to_row": 6, "attack_to_col": 4,
    "move_to_row": 5, "move_to_col": 4,
    "result": {
      "damage": 50,
      "type_multiplier": 1.0,
      "target_hp_before": 200,
      "target_hp_after": 150,
      "captured": false
    }
  },
  {
    "turn": 6,
    "player": "BLUE",
    "action_type": "foresight",
    "piece_id": "550e8400-e29b-41d4-a716-446655440007",
    "from_row": 7, "from_col": 3,
    "to_row": 7, "to_col": 3,
    "result": {
      "target_row": 4, "target_col": 3,
      "damage": 120,
      "resolves_on_turn": 8
    }
  },
  {
    "turn": 8,
    "player": "BLUE",
    "action_type": "foresight_resolve",
    "piece_id": "550e8400-e29b-41d4-a716-446655440007",
    "result": {
      "target_row": 4, "target_col": 3,
      "damage": 120,
      "target_piece_id": "550e8400-e29b-41d4-a716-446655440003",
      "target_hp_before": 160,
      "target_hp_after": 40,
      "captured": false
    }
  },
  {
    "turn": 9,
    "player": "RED",
    "action_type": "evolve",
    "piece_id": "550e8400-e29b-41d4-a716-446655440000",
    "from_row": 0, "from_col": 4,
    "to_row": 0, "to_col": 4,
    "result": {
      "from_species": "PIKACHU",
      "to_species": "RAICHU",
      "hp_restored": 50
    }
  },
  {
    "turn": 10,
    "player": "BLUE",
    "action_type": "trade",
    "piece_id": "550e8400-e29b-41d4-a716-446655440008",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440009",
    "from_row": 7, "from_col": 3,
    "to_row": 7, "to_col": 4,
    "result": {
      "item_given": "BENTSPOON",
      "item_received": "THUNDERSTONE",
      "triggered_evolution": true,
      "evolved_to": "JOLTEON"
    }
  },
  {
    "turn": 11,
    "player": "RED",
    "action_type": "release",
    "piece_id": null,
    "from_row": 3, "from_col": 4,
    "result": {
      "released_piece_id": "550e8400-e29b-41d4-a716-446655440001",
      "released_hp": 200
    }
  }
]
```

**`action_type` values:**

| Value | Engine `ActionType` | Description |
|---|---|---|
| `move` | `MOVE` | Standard reposition; also covers Safetyball storing an ally — check `result.stored` |
| `attack` | `ATTACK` (named piece) | Deterministic HP combat |
| `pokeball_attack` | `ATTACK` (Pokéball piece) | 50% RNG capture; `rng_roll` and `captured` always recorded |
| `masterball_attack` | `ATTACK` (Masterball piece) | Guaranteed capture; `captured` always true |
| `quick_attack` | `QUICK_ATTACK` | Eevee: attack then reposition in the same turn |
| `release` | `RELEASE` | Safetyball releases its stored Pokémon |
| `evolve` | `EVOLVE` | King evolution (costs the turn) |
| `foresight` | `FORESIGHT` | Mew/Espeon schedules a delayed attack |
| `foresight_resolve` | *(auto, turn start)* | App-injected entry when pending Foresight fires; not a player-chosen action |
| `trade` | `TRADE` | Free item swap with adjacent teammate (may trigger Eevee auto-evolution) |

---

### `bots.params` (JSONB)

See the `bots` table section above for the full example and parameter reference.

---

## Key Design Decisions

### No DynamoDB
At 5–20 users, DynamoDB adds operational complexity with zero benefit. PostgreSQL JSONB on RDS handles semi-structured game state natively, with full ACID, foreign keys, and a single system to operate. JSONB is fully supported on all current AWS RDS PostgreSQL versions.

### State format is `GameState.to_dict()` / `from_dict()`
The `games.state` JSONB is the direct output of `GameState.to_dict()` (defined in `engine/state.py`) and is consumed by `GameState.from_dict()`. Field names, types, and structure mirror the engine's dataclasses exactly. A separate human-readable notation (PokeChess-PGN) is designed in `docs/PokeChess Notation Design...pdf` and is a future display/replay feature — not the Postgres storage format.

### Coordinates are row/col integers, not algebraic notation
All positions in `games.state` and `games.move_history` use `row`/`col` integers (0–7), matching the engine's internal representation. Row 0 is Red's back rank; row 7 is Blue's. The frontend converts to algebraic notation (e.g. `e4`) for display. Keeping storage in engine-native coordinates eliminates a translation layer and avoids a class of off-by-one errors.

### `pokemon_pieces.id` === `piece.id` in state JSON
The same UUID is used in the Postgres row, in `state.board[]` piece objects, and in every relevant `move_history` entry. No translation layer needed for XP attribution. At game creation the app server injects each named piece's UUID into `Piece.id` before serializing the initial state. Pawns (Pokéballs, Safetyballs) have `id: null` — they are ephemeral and not tracked in `pokemon_pieces`.

### Earned XP vs applied XP are separate
`xp_earned` records raw activity, always. `xp_applied` and `xp_skip_reason` record what the business rule decided. Currently: wins apply XP, losses/draws/resigns skip it. This rule can change without touching historical data. The `xp_applied_at` timestamp makes the rollup idempotent — safe to retry.

### App server uses engine functions directly for state transitions
The app server imports `engine/` (the shared game logic package) and calls `GameState.from_dict()`, `get_legal_moves()`, `apply_move()`, and `is_terminal()` directly. It does not delegate move application or validation to the MCTS engine container — only MCTS search is offloaded (PvB only). This keeps the engine container stateless with respect to game logic and eliminates a network round-trip for every human move. The `games.state` JSONB is opaque only to the database — the app always deserializes it before use.

### Frequently queried fields are real columns
`status`, `whose_turn`, `winner`, `is_bot_game` live as real columns on the `games` row. Polling `GET /games/{id}` to check whose turn it is does not touch TOAST values. Only reads that need the full board state or history fetch the JSONB columns.

### Bots are separate from users
Bots have their own table with a JSONB `params` column for engine tuning. v1 ships with one bot row. Adding difficulty variants = new rows, no schema change. The `bot_side` column on `games` is stored for rendering convenience; it's also implicit (whichever player slot is null is the bot's side).

### `user_settings` is a proper table, not JSONB
Known settings (e.g. `board_theme`) get explicit columns with types and defaults. `extra_settings JSONB` is a catch-all for evolving/experimental settings. When a setting stabilizes, promote it to a column with a single migration. Migration cost from pure JSONB to a table would also be trivial at this scale.

### TOAST is transparent
PostgreSQL automatically compresses and stores out-of-line any JSONB value above ~2 KB. `move_history` will cross this threshold after ~40 moves. No configuration required; RDS autovacuum handles maintenance. Reads that don't need the JSONB columns (metadata queries) don't pay the TOAST I/O cost.

---

## Move Lifecycle Flow

```
1. Frontend sends:
   POST /games/{game_id}/move
   { "piece_row": 1, "piece_col": 4, "action_type": "MOVE",
     "target_row": 3, "target_col": 4 }

   Note: the frontend only presents legal moves (pre-fetched via
   GET /games/{id}/legal_moves), so every submitted move should be legal.
   The app still validates as a security baseline.

2. App server:
   a. Validates auth, confirms it's the player's turn (games.whose_turn)
   b. Fetches games.state JSONB
   c. Deserializes: state = GameState.from_dict(games.state)
   d. Validates submitted move is in get_legal_moves(state)

3. App applies the human's move using the shared engine library:
   outcomes = apply_move(state, move)
   if len(outcomes) == 2:           # Pokéball — stochastic
       roll = random.random()
       new_state = outcomes[0][0] if roll < 0.5 else outcomes[1][0]
       # record rng_roll in the move_history entry
   else:
       new_state = outcomes[0][0]

4. App checks if Foresight resolved this turn (pending_foresight was set
   in state and is now cleared in new_state). If so, prepend a
   "foresight_resolve" entry to the history batch before the player's move.

5. App builds the move_history entry from the old vs new state diff,
   then checks for game end:
   done, winner = is_terminal(new_state)

6. PvB only, if not done: app calls the MCTS engine for the bot's move
   POST localhost:5001/move
   { "state": GameState.to_dict(new_state),
     "time_budget": bot.params.time_budget }

7. Engine (internal) returns the bot's chosen move:
   { "piece_row": 0, "piece_col": 3, "action_type": "ATTACK",
     "target_row": 1, "target_col": 4, "move_slot": null, ... }

8. App applies bot move (same as step 3), builds its move_history entry,
   checks is_terminal(bot_state). Repeat Foresight-resolve check (step 4).

9. App writes back to Postgres (single UPDATE):
   - games.state        ← GameState.to_dict(final_state)   (overwrite)
   - games.move_history ← append new entry/entries          (jsonb concatenation)
   - games.whose_turn   ← flipped
   - games.turn_number  ← incremented
   - games.updated_at   ← now()
   - games.status       ← 'complete' if terminal
   - games.winner       ← 'red'|'blue'|'draw' if game over
   - games.end_reason   ← set if game over

10. On game completion only — app server also writes:
    - game_pokemon_map.xp_earned      ← tallied from move_history
    - game_pokemon_map.xp_applied     ← set by win/loss rule
    - game_pokemon_map.xp_skip_reason ← set if not applied
    - game_pokemon_map.xp_applied_at  ← now()
    - pokemon_pieces.xp               ← incremented
    - pokemon_pieces.evolution_stage  ← updated if threshold crossed
    - pokemon_pieces.species          ← updated if evolved during game

11. Frontend polls GET /games/{game_id}
    Receives: status, whose_turn, winner (real columns — no TOAST hit)
    + state JSON for board rendering (TOAST fetch, transparent)

    For move highlighting:
    GET /games/{game_id}/legal_moves?piece_row=3&piece_col=4
    App deserializes state, calls get_legal_moves(state), filters for
    the requested piece, returns list of {target_row, target_col, action_type}.
```

---

## Future Extensibility Notes

### Single-player campaign
A campaign feature would add tables like `campaigns`, `campaign_stages`, and `campaign_progress` (FK to `users.id`). Pokémon XP continuity would be handled through the existing `pokemon_pieces` table — no changes needed there. The current schema imposes no constraints that would complicate this.

### Multiple bots / difficulty tiers
Already handled. New bot difficulty = new row in `bots` with different `params` values. The `bot_id` FK on `games` handles it with no schema change.

### Game replay
Already partially supported. `move_history` stores all the data needed to replay a game. A custom PokéChess notation (in progress separately) would make this more compact and human-readable when the replay UI is built.

### Emoji reactions (future)
Could be added as an optional field on move_history entries or as a separate `game_reactions` table (FK to `games.id` + `users.id`). No existing tables need to change.

### Expanded settings
Add columns to `user_settings` as features stabilize. The `extra_settings JSONB` catch-all prevents the need for speculative columns upfront.

### ELO / leaderboards
Would add an `elo_history` table (FK to `users.id` + `games.id`) and an `elo` column on `users`. No existing tables need to change.

---

*End of data model reference.*
