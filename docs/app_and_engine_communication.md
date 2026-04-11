# App and engine communication

**Status:** Aligned with [`app/engine_client.py`](../app/engine_client.py) and [architecture_design_plan.md](architecture_design_plan.md). **Code wins** if anything drifts.

**Last updated:** April 2026

---

## Deployment

`pokechess-app` and `pokechess-engine` run as **two ECS tasks on the same EC2 instance**. They communicate over **`localhost`** (port **5001** for the engine), matching `ENGINE_URL` defaults (e.g. `http://localhost:5001` in [`docker-compose.yml`](../docker-compose.yml)). The engine port is **not** exposed to the public internet.

Infrastructure-as-code may live in this repo or elsewhere; there is no requirement that a `terraform/` tree exist in every checkout.

---

## Engine HTTP contract (authoritative)

The app calls **`POST /move`** only. Payload shape matches `request_bot_move()`:

```json
{
  "state": { "...": "wire GameState dict" },
  "persona_params": {
    "time_budget": 1.5
  }
}
```

- **`time_budget`** (seconds) is required inside `persona_params` for MCTS. The app may **adjust** it for load-aware budgeting ([load_aware_budgeting.md](load_aware_budgeting.md)).
- Other keys in `persona_params` are forwarded for future tuning; unknown keys should be ignored by the engine.

**Response:** A **flat** JSON object the app maps into `Move` (e.g. `piece_row`, `piece_col`, `action_type`, `target_row`, `target_col`, optional `secondary_row` / `secondary_col`, `move_slot`). **Not** wrapped as `{ "move": { ... } }` unless the implementation changes and the app is updated.

The engine **never** calls the app, **never** uses **RDS**, and **never** receives game persistence work from the app beyond the state blob in each `/move` request.

---

## Persistence boundaries

| Concern | Where it lives |
|--------|----------------|
| Users, games, `games.state`, `move_history`, roster, bots, etc. | **Amazon RDS (PostgreSQL)** — accessed **only** by `pokechess-app` |
| In-flight MCTS trees | Engine process RAM |
| Bot-only persistence (e.g. transposition tables) | **Engine / bot server** — e.g. **local SQLite** inside the engine container; **not** RDS |

There is **no** `POST /backup` from the app and **no** app-orchestrated S3 backup for the engine. Persistence beyond `/move` is **the bot server’s responsibility** inside the engine container.

---

## Concurrency

The engine processes **`POST /move`** through a **queue-style model**: work is handled **one search at a time** per instance (requests **wait** when busy). That matches sharing CPU fairly under load and complements app-side **load-aware `time_budget`** scaling.

---

## Load-aware budget scaling (app-side)

Before `POST /move`, the app may set `persona_params["time_budget"]` to `base_budget / N` for concurrent human players against the same bot. See [load_aware_budgeting.md](load_aware_budgeting.md).
