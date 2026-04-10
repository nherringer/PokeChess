Here's the revised v1 plan:

---

## Architecture Decision — PokeChess v1

**Repo:** **Single monorepo** — one repository contains `engine/`, `bot/`, `cpp/`, `app/`, `tests/`, `docs/`, and two Dockerfiles (`Dockerfile.app`, `Dockerfile.engine`). CI/CD builds **two container images from this repo** on each merge to main (for example two pipeline jobs or a matrix). This matches [implementation_roadmap.md](implementation_roadmap.md) (“monorepo, two Dockerfiles”). Optional infrastructure-as-code (e.g. Terraform) may live alongside the app in this repo or in a small dedicated infra repository; it provisions **those two images**, not three separate application codebases.

**Compute:** Single EC2 t4g.small (free until Dec 31 2026, ~$12.26/mo after) running two ECS services via ECS on EC2:

- `pokechess-app` — FastAPI game server (port 8000); handles all client requests, move validation, game state, PvP/PvB routing
- `pokechess-engine` — FastAPI wrapper around MCTS bot (Python + C++ pybind11, port 5001); internal only, not publicly exposed

**Communication:**

- Browser → app: HTTP polling or SSE (1–3s latency acceptable)
- App → engine: `POST localhost:5001/move` with full game state and time budget; engine returns best move. `POST localhost:5001/backup` triggers tree serialization to S3. Engine never initiates requests or accesses Postgres.

**Engine state:** MCTS search trees held in RAM, keyed by `game_id`. On game completion (or on any schedule/event the app deems appropriate), the app calls `/backup` to serialize tree snapshots to S3. On container startup, the engine loads available snapshots from S3 into RAM before accepting requests. S3 lifecycle rules expire old snapshots automatically.

**Request queue:** Multiple incoming move requests are handled with a **queue** (e.g. FIFO), not parallel MCTS across many threads. FastAPI/`asyncio` can still accept connections without blocking the event loop, but the engine **drains the queue one search at a time** per instance so two games never compete for CPU inside simultaneous full searches. Under load, backlog shows up as **queue depth and wait time**, not as splitting strength across concurrent searches. See [load_aware_budgeting.md](load_aware_budgeting.md) for time budgets and back-pressure. pybind11 still releases the GIL in C++ hot loops; the architecture choice here is **serialization via a queue**, not `ThreadPoolExecutor` parallelism.

**Storage:** Postgres on EC2 — users, history, ELO, and active game state (JSONB for complex/nested structures like board state, HP, turns). Single database, single connection pool, single backup strategy.

**Frontend:** React/Next.js — S3 + CloudFront (target; not required for local backend development).

**CI/CD:** From the **monorepo**, build and push **two** images (`pokechess-app`, `pokechess-engine`) to ECR, then update the corresponding ECS services. App and engine deploys can stay decoupled (different workflows or manual promotion) while still sourcing from one repository.

**Estimated cost:** ~$3–5/mo until Jan 2027; ~$16–19/mo after (DynamoDB removed from the stack reduces this further — no per-request costs or provisioned capacity to worry about)

**Deferred to v2:** Split `pokechess-engine` onto dedicated compute-optimized instance, on-demand engine start/stop
