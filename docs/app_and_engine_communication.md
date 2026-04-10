Here's the updated plan with DynamoDB removed and Postgres JSONB handling everything:

---

## Architecture Decision — pokechess-engine / Backend Integration

**Deployment:** `pokechess-app` and `pokechess-engine` run as two independent ECS services on the same EC2 t4g.small, communicating exclusively over `localhost`. The engine port (5001) is not publicly exposed. Each service has its own Docker image, ECR repo, and independent CI/CD pipeline. Infrastructure for both is managed via `pokechess-terraform`.

**Engine API (FastAPI):** The engine exposes a lightweight FastAPI layer:

- `POST /move` — the **bot contract endpoint**.  Accepts the current game state
  and a `persona_params` dict; runs MCTS; returns the best move.  Payload shape:
  ```json
  {
    "state":          { "<FEN dict>" },
    "persona_params": { "time_budget": 1.5, "exploration_c": 1.41 }
  }
  ```
  Response: `{ "move": { "<Move dict>" } }`.
  Only `time_budget` (float, seconds) is required in `persona_params`; unknown
  keys must be silently ignored.  See `docs/bot_api_design.txt` for the full
  contract.

The engine never initiates requests to the app and never touches Postgres. All
game state required for a search is passed directly in the `/move` payload.
The engine is a pure responder.

**Load-aware budget scaling (app-side only):** Before calling `POST /move`, the
app computes an *effective* `time_budget = base_budget / N`, where N is the
number of distinct players currently active against the same bot personality.
The engine receives the already-adjusted value inside `persona_params` and
behaves identically regardless — no engine changes are required.  See
`docs/load_aware_budgeting.md` for the full design and configuration.

**S3 — Transposition Table Persistence:**

- On container startup, the engine loads any available tree snapshots from S3 into RAM before accepting requests
- `POST /backup` writes current tree snapshots to `s3://pokechess-trees/backup` (or similar) — triggered by the app on game completion, or on any other schedule/event the app deems appropriate
- S3 lifecycle rules expire old snapshots automatically

**Concurrency:** The engine uses `asyncio` for non-blocking request handling alongside a `ThreadPoolExecutor (max_workers=3–5)` for parallelized MCTS searches. Python's GIL is not a concern — pybind11 releases the GIL on entry to C++ hot loops, enabling genuine parallel CPU execution across concurrent search threads. Multiple simultaneous PvB games intentionally share compute — the engine splits its search capacity across all active games, naturally scaling down per-game strength under load. This is a deliberate design choice: players teaming up in PvP against the engine experience a shared challenge where collectively pressuring it degrades its performance across the board.

**Data ownership:**

| Concern | Owner |
|---|---|
| Game state (board, HP, turns) | `pokechess-app` → Postgres (JSONB) |
| MCTS search trees (in-flight) | `pokechess-engine` → RAM |
| MCTS tree snapshots (persistent) | `pokechess-engine` → S3 |
| User data, history, ELO | `pokechess-app` → Postgres |
