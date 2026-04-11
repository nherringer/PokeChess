# Local Testing Runbook

Two modes: **Partial** (no bot — PvP only) and **Full** (with bot — PvP + PvB).

For automated setup, see [Makefile commands](#makefile-commands) at the bottom.

---

## Installation (macOS)

Do this once before anything else.

### 1. Homebrew

The package manager used for everything below.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the printed instructions to add `brew` to your PATH (the installer tells you exactly what to run).

### 2. Docker Desktop

Manages all containers and includes Docker Compose.

```bash
brew install --cask docker
```

Then open **Docker Desktop** from Applications and let it finish starting. Verify:

```bash
docker --version
docker compose version
```

### 3. Make

Ships with Xcode Command Line Tools (likely already installed). If `make` is not found:

```bash
xcode-select --install
```

### 4. Python 3.12+

The project venv uses Python 3.14. Install via Homebrew:

```bash
brew install python@3.14
```

> Any 3.12+ will work. Use `python3.14` (or `python3.12`, etc.) explicitly in the venv command below.

### 5. Node 20+

```bash
brew install node@20
brew link node@20 --force
```

Verify: `node --version` should print `v20.x.x` or higher.

### 6. Set up the Python venv

From the `PokeChess/` directory:

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r app/requirements.txt
```

### 7. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

### Done

Verify everything is in order:

```bash
docker --version          # Docker version 27+
make --version            # GNU Make 3.81+
.venv/bin/python --version  # Python 3.14+
node --version            # v20+
```

---

## Prerequisites summary

- Docker Desktop running
- `.venv/` set up with `pip install -r app/requirements.txt`
- `frontend/node_modules/` populated via `npm install`

No local `psql` required — schema is applied via `docker compose exec`.

---

## Local vs. AWS: secrets and gotchas

| Config | Local (dev) | AWS (prod) |
|--------|-------------|------------|
| `DATABASE_URL` | `postgresql+asyncpg://pokechess:pokechess@localhost:5432/pokechess` | RDS endpoint + Secrets Manager credentials |
| `ENGINE_URL` | `http://localhost:5001` | `http://localhost:5001` — **same**: ECS uses `network_mode=host` |
| `SECRET_KEY` | dev default (hardcoded, warns on startup) | Secrets Manager injected via ECS task env |
| `CORS_ORIGINS` | `*` (allowed when `ENVIRONMENT=development`) | Must be explicit domain — app raises `RuntimeError` if `*` and not development |
| `ENVIRONMENT` | `development` (default) | Must be set to `production` to enforce CORS + `Secure` cookie flag |
| `S3_TREE_BUCKET` / `AWS_DEFAULT_REGION` | Not needed — engine skips TT backup | Set in ECS task def for the engine container |

**Specific gotchas:**

1. **RDS requires SSL.** `asyncpg_dsn()` in `app/config.py` strips the SQLAlchemy prefix but adds no SSL params. The prod `DATABASE_URL` will need `?ssl=require` appended (or set via asyncpg connection kwargs) — this is not wired up yet.

2. **Refresh token cookie `Secure` flag.** `auth.py` sets `secure=config.ENVIRONMENT != "development"`. Locally this is `False` (works over HTTP). In prod it's `True` (HTTPS only). If you test with `ENVIRONMENT=production` locally over plain HTTP, login/register will silently fail to set the refresh cookie.

3. **`ENGINE_URL` is the same everywhere.** Both local full-stack and prod ECS run the app and engine on the same host (`network_mode=host`), so `http://localhost:5001` works identically. No env var change needed when moving to prod.

4. **DB schema is not auto-applied.** Must be run manually after first `docker compose up`, both locally and on RDS after provisioning.

5. **Bot UUID is random on each schema apply.** `app/db/schema.sql` seeds `Metallic` with `gen_random_uuid()`. The frontend hardcodes bot IDs in `lib/constants.ts` (all empty). Until a `GET /bots` endpoint ships, you must look up the UUID after applying the schema and fill in `BOT_IDS` manually (see `make bot-id`).

---

## 1. Partial Integration Testing (no bot — PvP only)

Tests: auth, PvP games, friends, invites, roster. PvB move submission returns `503 engine_unavailable` — all other routes are unaffected.

**Terminal 1 — postgres + app:**
```bash
make partial        # starts postgres, waits for healthy, applies schema
make app            # starts uvicorn on :8000 (foreground)
```

**Terminal 2 — frontend:**
```bash
make frontend       # starts Next.js on :3000 (foreground)
```

Verify the app is up: `curl http://localhost:8000/health` → `{"status":"ok"}`

**Teardown:**
```bash
make down           # stops postgres, keeps DB volume
make reset          # stops postgres AND wipes DB volume (full clean slate)
```

---

## 2. Full Integration Testing (PvP + PvB)

> **Blocked until `bot/server.py` is implemented.** See `docs/implementation_roadmap.md`.

`Dockerfile.engine` runs `uvicorn bot.server:app`. That module does not exist yet — the engine container crashes on start.

**When `bot/server.py` is ready:**

**Terminal 1 — all services:**
```bash
make full           # docker compose up --build (all 3 services), applies schema
```

**Terminal 2 — frontend:**
```bash
make bot-id         # prints the seeded Metallic UUID — paste into frontend/lib/constants.ts BOT_IDS
make frontend       # starts Next.js on :3000 (foreground)
```

**Teardown:**
```bash
make down           # or make reset for full wipe
```

---

## Unit / pytest tests (no Docker needed)

```bash
make test           # all tests
make test-v         # verbose
```

Covers engine logic, MCTS, and app game logic. No Postgres or engine server required.

---

## Makefile commands

| Command | What it does |
|---------|-------------|
| `make partial` | Start postgres, wait for healthy, apply schema |
| `make full` | `docker compose up --build` all services, apply schema |
| `make app` | Run uvicorn app server on :8000 (foreground) |
| `make frontend` | Run Next.js dev server on :3000 (foreground) |
| `make schema` | Apply `app/db/schema.sql` (re-run safe — errors on existing objects are non-fatal) |
| `make bot-id` | Print the seeded Metallic bot UUID from the DB |
| `make test` | Run pytest |
| `make test-v` | Run pytest verbose |
| `make down` | `docker compose down` (keeps volume) |
| `make reset` | `docker compose down -v` (wipes DB volume) |
