# Local Testing Runbook

Two modes: **Partial** (no bot — PvP only) and **Full** (with bot — PvP + PvB).

---

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ with a venv at `PokeChess/.venv` (or `pip install -r app/requirements.txt`)
- Node 20+ (for frontend)
- `psql` CLI

All commands assume your working directory is `PokeChess/` unless noted.

---

## 1. Partial Integration Testing (no bot server)

Tests: auth, PvP games, friends, invites, roster. PvB game creation will fail at the move submission step (engine unreachable), but everything else works.

### Step 1 — Start Postgres

```bash
docker compose up postgres -d
```

Wait a few seconds for it to be healthy (`docker compose ps` should show `healthy`).

### Step 2 — Apply the DB schema

```bash
psql postgresql://pokechess:pokechess@localhost:5432/pokechess -f app/db/schema.sql
```

This also seeds the `Metallic` bot row. Run once; re-running against an existing DB will error on duplicate constraints — that's fine, schema is already applied.

### Step 3 — Run the app server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The app starts fine without the engine running. Any request that triggers a bot move will return a `503 engine_unavailable` — all non-PvB routes are unaffected.

Verify: `curl http://localhost:8000/health` → `{"status":"ok"}`

### Step 4 — Run the frontend

```bash
cd frontend
npm run dev
```

Frontend runs at **http://localhost:3000** and talks to the app at `http://localhost:8000` (set in `.env.local`).

### Teardown

```bash
# Stop app (Ctrl+C) and frontend (Ctrl+C), then:
docker compose down         # stops postgres, keeps volume
docker compose down -v      # stops postgres AND wipes the DB volume
```

---

## 2. Full Integration Testing (with bot — PvP + PvB)

> **Blocked until `bot/server.py` is implemented.** See `docs/implementation_roadmap.md`.

`Dockerfile.engine` runs `uvicorn bot.server:app --host 0.0.0.0 --port 5001`. That module does not yet exist.

### When `bot/server.py` is ready:

### Step 1 — Build and start all services

```bash
docker compose up --build
```

This starts `postgres`, `pokechess-engine` (port 5001), and `pokechess-app` (port 8000) together. The app waits for postgres to be healthy before starting.

### Step 2 — Apply the DB schema

```bash
psql postgresql://pokechess:pokechess@localhost:5432/pokechess -f app/db/schema.sql
```

### Step 3 — Wire up the bot ID in the frontend

The `Metallic` bot is seeded with a random UUID on schema apply. The frontend hardcodes bot IDs in `lib/constants.ts` (all empty until filled in). Until a `GET /bots` endpoint ships, you must look up the UUID manually:

```bash
psql postgresql://pokechess:pokechess@localhost:5432/pokechess \
  -c "SELECT id FROM bots WHERE name = 'Metallic';"
```

Paste that UUID into all five `BOT_IDS` entries in `frontend/lib/constants.ts`.

### Step 4 — Run the frontend

```bash
cd frontend
npm run dev
```

Frontend at **http://localhost:3000**. All game modes (PvP and PvB) should now be testable.

### Teardown

```bash
docker compose down         # keeps postgres volume
docker compose down -v      # wipes postgres volume (full reset)
```

---

## Unit / pytest tests (no Docker needed)

```bash
source .venv/bin/activate
pytest                          # all tests
pytest tests/test_moves.py      # single file
pytest tests/test_moves.py::test_name -v   # single test
```

The test suite covers engine logic, MCTS, and app game logic. No Postgres or engine server required.
