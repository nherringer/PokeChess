Here's the revised v1 plan:

---

## Architecture Decision — PokeChess v1

**Repo:** **Single monorepo** — one repository contains `engine/`, `bot/`, `cpp/`, `app/`, `tests/`, `docs/`, and two Dockerfiles (`Dockerfile.app`, `Dockerfile.engine`). CI/CD builds **two container images from this repo** on each merge to main (for example two pipeline jobs or a matrix). This matches [implementation_roadmap.md](implementation_roadmap.md) (“monorepo, two Dockerfiles”). Optional infrastructure-as-code (e.g. Terraform) may live alongside the app in this repo or in a small dedicated infra repository; it provisions **those two images**, not three separate application codebases.

**Compute:** Single EC2 t4g.small (free until Dec 31 2026, ~$12.26/mo after) running two ECS services via ECS on EC2:

- `pokechess-app` — FastAPI game server (port 8000); handles all client requests, move validation, game state, PvP/PvB routing
- `pokechess-engine` — FastAPI wrapper around MCTS bot (Python + C++ pybind11, port 5001); internal only, not publicly exposed

**Communication:**

- Browser → app: HTTP polling or SSE (1–3s latency acceptable)
- App → engine: With **both ECS tasks on the same EC2 host**, the app reaches the engine at **`http://localhost:5001`** (or whatever `ENGINE_URL` is set to — same idea as `docker-compose.yml`). **Only** `POST /move` is part of the app–engine contract ([`app/engine_client.py`](../app/engine_client.py)). There is **no** app-triggered `POST /backup` and **no** plan for the app to orchestrate engine persistence to external stores.

**Engine process:** The **bot server** owns transposition-table and related persistence **inside the engine container** (e.g. **local SQLite** — does **not** use RDS). The app **never** connects to that store; game state for users remains in **RDS** only.

**Engine state (in-flight):** MCTS search trees in RAM while searching.

**Request queue:** A **queue** (or pool drained **one request at a time**): incoming `POST /move` work waits in line; **one MCTS search runs at a time** per engine instance so games do not compete for CPU inside overlapping full searches. Backlog shows up as **wait time / queue depth**. Pair with [load_aware_budgeting.md](load_aware_budgeting.md) for app-side `time_budget` scaling. This replaces any older “parallel ThreadPoolExecutor across many searches” description.

**Storage — app:** **Amazon RDS for PostgreSQL** — all application tables (`users`, `games`, `pokemon_pieces`, etc.). The FastAPI app uses `DATABASE_URL` to RDS only. **Not** “Postgres on the same EC2 box” for production app data in this target.

**Storage — engine:** Bot-local persistence (e.g. SQLite on disk in the engine container) for MCTS/TT data **only**; **no RDS** access from the engine.

**Frontend:** React/Next.js — static hosting on S3 + CloudFront (target; not required for local backend development). (Unrelated to engine TT storage.)

**CI/CD:** From the **monorepo**, build and push **two** images (`pokechess-app`, `pokechess-engine`) to ECR, then update the corresponding ECS services. App and engine deploys can stay decoupled (different workflows or manual promotion) while still sourcing from one repository. **Target** pipeline — not necessarily present in-repo yet.

**Estimated cost:** ~$3–5/mo until Jan 2027; ~$16–19/mo after (figures are **approximate**; RDS, EBS, transfer, and region change totals.)

**Deferred to v2:** Split `pokechess-engine` onto dedicated compute-optimized instance, on-demand engine start/stop
