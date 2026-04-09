Here's the revised v1 plan:

---

## Architecture Decision — PokeChess v1

**Repos:** Three repositories — `pokechess-app`, `pokechess-engine`, and `pokechess-terraform` (manages all infrastructure for both services).

**Compute:** Single EC2 t4g.small (free until Dec 31 2026, ~$12.26/mo after) running two ECS services via ECS on EC2:

- `pokechess-app` — FastAPI game server (port 8000); handles all client requests, move validation, game state, PvP/PvB routing
- `pokechess-engine` — FastAPI wrapper around MCTS bot (Python + C++ pybind11, port 5001); internal only, not publicly exposed

**Communication:**

- Browser → app: HTTP polling or SSE (1–3s latency acceptable)
- App → engine: `POST localhost:5001/move` with full game state and time budget; engine returns best move. `POST localhost:5001/backup` triggers tree serialization to S3. Engine never initiates requests or accesses Postgres.

**Engine state:** MCTS search trees held in RAM, keyed by `game_id`. On game completion (or on any schedule/event the app deems appropriate), the app calls `/backup` to serialize tree snapshots to S3. On container startup, the engine loads available snapshots from S3 into RAM before accepting requests. S3 lifecycle rules expire old snapshots automatically.

**Concurrency:** `asyncio` for non-blocking request handling with `ThreadPoolExecutor(max_workers=3–5)` for parallelized MCTS searches. Python's GIL is not a concern — pybind11 releases the GIL on entry to C++ hot loops, enabling genuine parallel CPU execution across concurrent search threads. Multiple simultaneous PvB games intentionally share compute — the engine splits its search capacity across all active games, naturally scaling down per-game strength under load. This is a deliberate design choice: players teaming up against the engine experience a shared challenge where collectively pressuring it degrades its performance across the board.

**Storage:** Postgres on EC2 — users, history, ELO, and active game state (JSONB for complex/nested structures like board state, HP, turns). Single database, single connection pool, single backup strategy.

**Frontend:** React/Next.js — S3 + CloudFront

**CI/CD:** Two independent GitHub Actions pipelines (one per app/engine repo) → ECR → ECS service update. `pokechess-terraform` manages shared infra. Engine pipeline owned by ML engineer; decoupled from app deploys.

**Estimated cost:** ~$3–5/mo until Jan 2027; ~$16–19/mo after (DynamoDB removed from the stack reduces this further — no per-request costs or provisioned capacity to worry about)

**Deferred to v2:** Split `pokechess-engine` onto dedicated compute-optimized instance, on-demand engine start/stop
