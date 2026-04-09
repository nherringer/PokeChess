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

The app server (FastAPI) is the only process that touches the database. The engine container is internal-only — the app server calls it via HTTP, passes the current game state, and gets back a new state. The frontend never talks to the engine directly.

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

Overwritten on every move. This is the complete snapshot the engine needs to resume the game cold. The app server treats this as an opaque blob — it stores it, returns it to the frontend for rendering, and sends it to the engine. The app never parses the internals.

**Size:** ~5–6 KB at full board (26–32 pieces + foresight queue). Fixed size per game. Stored inline by Postgres (below TOAST threshold).

```json
{
  "turn_number": 6,
  "whose_turn": "blue",
  "pieces": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "pokemon": "raichu",
      "role": "king",
      "team": "red",
      "square": "e1",
      "hp": 220,
      "max_hp": 250,
      "held_item": null,
      "stored_piece_id": null,
      "on_board": true
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "pokemon": "safetyball",
      "role": "pawn",
      "team": "red",
      "square": "e4",
      "hp": null,
      "max_hp": null,
      "held_item": null,
      "stored_piece_id": "550e8400-e29b-41d4-a716-446655440002",
      "on_board": true
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "pokemon": "charmander",
      "role": "knight",
      "team": "red",
      "square": null,
      "hp": 160,
      "max_hp": 200,
      "held_item": null,
      "stored_piece_id": null,
      "on_board": false
    }
  ],
  "foresight_queue": [
    {
      "caster_id": "550e8400-e29b-41d4-a716-446655440010",
      "target_square": "d5",
      "resolves_on_turn": 7
    }
  ]
}
```

**State field reference:**

| Field | Type | Notes |
|---|---|---|
| `turn_number` | int | Increments each half-turn |
| `whose_turn` | string | `'red'` or `'blue'` |
| `pieces[]` | array | All pieces including captured and stored |
| `piece.id` | UUID | Same as `pokemon_pieces.id` for named pieces |
| `piece.square` | string | Algebraic notation (`'e4'`), null if off-board |
| `piece.hp` | int | null for Pokéballs (no HP) |
| `piece.stored_piece_id` | UUID | ID of piece stored inside this Safetyball, or null |
| `piece.on_board` | bool | false = captured or stored |
| `foresight_queue[]` | array | Pending Foresight attacks, max 2 entries |

---

### `games.move_history` (JSONB)

Append-only array. One entry per action. RNG outcomes (Stealball rolls) are recorded here, not in `state`.

**Size estimates:**
- ~200 bytes per entry (average across action types)
- 100 moves → ~20 KB raw, ~10 KB compressed
- 500 moves → ~100 KB raw, ~50 KB compressed
- 1000 moves → ~200 KB raw, ~100 KB compressed (likely upper bound)

Postgres TOAST handles values above ~8 KB transparently — no configuration needed, no query changes required.

```json
[
  {
    "turn": 1,
    "player": "red",
    "action_type": "move",
    "piece_id": "550e8400-e29b-41d4-a716-446655440003",
    "from": "g1",
    "to": "f3",
    "result": {}
  },
  {
    "turn": 2,
    "player": "blue",
    "action_type": "attack",
    "piece_id": "550e8400-e29b-41d4-a716-446655440004",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440003",
    "from": "d7",
    "to": "f3",
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
    "player": "red",
    "action_type": "stealball_attack",
    "piece_id": "550e8400-e29b-41d4-a716-446655440005",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440004",
    "from": "a2",
    "to": "b3",
    "result": {
      "rng_roll": 0.73,
      "captured": false,
      "stealball_spent": true
    }
  },
  {
    "turn": 4,
    "player": "blue",
    "action_type": "safetyball_store",
    "piece_id": "550e8400-e29b-41d4-a716-446655440006",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440003",
    "from": "c7",
    "to": "f3",
    "result": {
      "stored_hp": 160,
      "stored_max_hp": 200
    }
  },
  {
    "turn": 5,
    "player": "red",
    "action_type": "evolve",
    "piece_id": "550e8400-e29b-41d4-a716-446655440000",
    "from": "e1",
    "to": "e1",
    "result": {
      "from_species": "pikachu",
      "to_species": "raichu",
      "hp_restored": 50
    }
  },
  {
    "turn": 6,
    "player": "blue",
    "action_type": "foresight",
    "piece_id": "550e8400-e29b-41d4-a716-446655440010",
    "from": "d8",
    "to": "d8",
    "result": {
      "target_square": "d5",
      "resolves_on_turn": 7
    }
  },
  {
    "turn": 7,
    "player": "red",
    "action_type": "item_trade",
    "piece_id": "550e8400-e29b-41d4-a716-446655440010",
    "target_piece_id": "550e8400-e29b-41d4-a716-446655440007",
    "from": "d1",
    "to": "e1",
    "result": {
      "item": "thunder_stone"
    }
  }
]
```

**`action_type` values:**

| Value | Description |
|---|---|
| `move` | Standard reposition, no combat |
| `attack` | HP-based combat, target may survive |
| `stealball_attack` | 50% RNG capture attempt; `rng_roll` recorded |
| `safetyball_store` | Safetyball moves onto injured ally to store them |
| `safetyball_release` | Stored Pokémon released manually |
| `evolve` | King evolution (costs a turn) |
| `foresight` | Mew/Espeon schedules delayed attack |
| `foresight_resolve` | Deferred foresight damage lands (auto, start of turn) |
| `item_trade` | Free action item swap with adjacent teammate |

---

### `bots.params` (JSONB)

See the `bots` table section above for the full example and parameter reference.

---

## Key Design Decisions

### No DynamoDB
At 5–20 users, DynamoDB adds operational complexity with zero benefit. PostgreSQL JSONB on RDS handles semi-structured game state natively, with full ACID, foreign keys, and a single system to operate. JSONB is fully supported on all current AWS RDS PostgreSQL versions.

### No FEN/PGN
Standard chess notation cannot represent HP, stored pieces, held items, foresight queue, or type state. Game state is stored as the engine's native JSON snapshot. A custom PokéChess notation is being designed separately and is a future display/replay feature — not a storage or engine concern.

### `pokemon_pieces.id` === `piece_id` in JSON
The same UUID is used in the Postgres row, in `state.pieces[]`, and in every `move_history` entry. No translation layer needed for XP attribution. At game creation, when `game_pokemon_map` rows are written, the `pokemon_piece_id` values are also embedded into the initial `state` JSON that gets sent to the engine.

### Earned XP vs applied XP are separate
`xp_earned` records raw activity, always. `xp_applied` and `xp_skip_reason` record what the business rule decided. Currently: wins apply XP, losses/draws/resigns skip it. This rule can change without touching historical data. The `xp_applied_at` timestamp makes the rollup idempotent — safe to retry.

### State is opaque to the app server
The app server stores `state`, returns it to the frontend for rendering, and sends it to the engine. It does not parse internals. This means the engine can evolve its internal state format without requiring app server changes, as long as the top-level game row columns (`whose_turn`, `status`, `winner`) remain stable.

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
   { "piece_id": "...", "from": "e2", "to": "e4", "action_type": "move" }

2. App server:
   a. Validates auth, confirms it's the player's turn (games.whose_turn)
   b. Fetches games.state (current board snapshot)

3. App server calls engine (internal):
   POST localhost:5001/move
   { "state": <current state JSON>, "move": <move payload> }

4. Engine returns:
   { "new_state": <updated state JSON>, "move_result": <result object> }

5. App server writes back to Postgres (single UPDATE):
   - games.state        ← new_state (overwrite)
   - games.move_history ← append move_result entry
   - games.whose_turn   ← flipped
   - games.turn_number  ← incremented
   - games.updated_at   ← now()
   - games.status       ← 'complete' if king eliminated
   - games.winner       ← set if game over
   - games.end_reason   ← set if game over

6. On game completion only — app server also writes:
   - game_pokemon_map.xp_earned  ← tallied from move_history
   - game_pokemon_map.xp_applied ← set by win/loss rule
   - game_pokemon_map.xp_skip_reason ← set if not applied
   - game_pokemon_map.xp_applied_at  ← now()
   - pokemon_pieces.xp           ← incremented
   - pokemon_pieces.evolution_stage  ← updated if threshold crossed
   - pokemon_pieces.species      ← updated if evolved during game

7. Frontend polls GET /games/{game_id}
   Receives: status, whose_turn, winner (real columns — no TOAST hit)
   + state JSON for board rendering (TOAST fetch, transparent)
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
