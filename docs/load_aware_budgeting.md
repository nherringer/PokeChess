# Load-Aware MCTS Budget Scaling

**Status:** Implemented  
**Last updated:** April 2026

---

## Problem

A single bot personality (e.g. "Metallic") can be playing against many human
players at the same time.  If every game independently gets the full MCTS
`time_budget` (e.g. 3 seconds), the engine container may be saturated, and the
bot effectively gets superhuman search time across the board — unfair to players
who get to it first.

The product intent is **collaborative pressure**: when many players fight the same
bot simultaneously, the shared compute is spread across all of them, so each game
receives a proportionally smaller search budget.

---

## Mechanism

### 1. Activity tracking

Every time a human player successfully submits a move in a PvB game, the app
upserts a row in `bot_player_activity`:

```sql
CREATE TABLE bot_player_activity (
    player_id     UUID      NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    bot_id        UUID      NOT NULL REFERENCES bots(id)   ON DELETE CASCADE,
    last_moved_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, bot_id)
);
CREATE INDEX idx_bpa_bot_time ON bot_player_activity (bot_id, last_moved_at);
```

One row per (player, bot) pair — `last_moved_at` is refreshed on every move.

### 2. Counting active players

Before calling the engine, the app counts how many distinct players are "active"
against this bot in the configured window:

```sql
SELECT COUNT(*) AS n
FROM   bot_player_activity
WHERE  bot_id        = $bot_id
  AND  last_moved_at > now() - ($window_minutes * interval '1 minute')
```

The current player has already been upserted, so N ≥ 1 always.

### 3. Effective budget

```
effective_time_budget = base_time_budget / N
```

`base_time_budget` comes from `bots.params->>'time_budget'` (stored in Postgres
alongside other bot configuration).  The effective budget is placed into
`persona_params["time_budget"]` before the HTTP call to the engine.

The engine honours whatever `time_budget` it receives — no engine-side changes
are required for this feature.

---

## Configuration

| Config key                 | Env variable                   | Default | Meaning                                                          |
|----------------------------|--------------------------------|---------|------------------------------------------------------------------|
| `BOT_ACTIVE_WINDOW_MINUTES`| `BOT_ACTIVE_WINDOW_MINUTES`    | `22`    | Minutes after last move that a player is counted as "active"    |

Set `BOT_ACTIVE_WINDOW_MINUTES` in the app container's environment.  A longer
window makes the bot weaker for longer after a burst of activity; a shorter
window recovers faster but provides less protection during a surge.

---

## Example

`bots.params = {"time_budget": 3.0}`, window = 22 min.

| Players active in window | Effective budget |
|--------------------------|-----------------|
| 1                        | 3.0 s           |
| 2                        | 1.5 s           |
| 5                        | 0.6 s           |
| 10                       | 0.3 s           |

The effective budget is further clamped to `[0.1, 10.0]` by `engine_client.py`
as a safety rail against DB misconfiguration. The upper bound was lowered from
30.0 to 10.0 to reduce worst-case Postgres lock duration (see known gap in
MASTERDOC.md §13).

---

## Scope

This is **app-side only**.  The bot/ML service receives a plain `persona_params`
dict with the adjusted `time_budget` and treats it like any other request.
No queuing, worker pools, or concurrency changes on the engine side are part of
this feature; those remain future work if needed.

---

## Data model reference

See `docs/pokechess_data_model.md` §Schema for table definitions and indexes.
The `bot_player_activity` table is defined in `app/db/schema.sql` alongside all other tables.  Apply with `psql $DATABASE_URL -f app/db/schema.sql`.
