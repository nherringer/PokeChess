# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PokeChess is a hybrid chess/Pokemon game. This repo contains the full backend stack: the ML bot (MCTS-based), the FastAPI application layer, and the Next.js frontend. The bot and app are deployed as separate containers on ECS.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_moves.py

# Run a single test
pytest tests/test_moves.py::test_name -v

# Win-rate benchmark (bot vs random, bot vs bot)
python scripts/benchmark.py                        # 20 games, 0.5s/move
python scripts/benchmark.py --budget 1.0 --games 50   # slower, more rigorous
```

No build step required for Python. The C++ extension is optional but strongly recommended for performance.

```bash
# Build C++ rollout extension (requires pybind11: pip install pybind11)
python setup.py build_ext --inplace

# The bot auto-detects the extension at import time; falls back to pure Python if not built.
```

## Architecture

```
engine/     Core game logic — no ML dependencies
  state.py    GameState, Piece, enums (PieceType, Team, Item, PokemonType)
  moves.py    Move dataclass + get_legal_moves(state) → List[Move]
  rules.py    apply_move() → [(state, prob)], is_terminal(), hp_winner()
  zobrist.py  Zobrist hashing for transposition table

bot/        MCTS bot HTTP service — deployed as the engine container
  mcts.py         MCTS tree, 4-phase loop, tree reuse between moves
  ucb.py          UCB1 formula with tunable exploration constant C
  transposition.py Persistent hash→(wins,visits) table across games
  server.py       FastAPI service: POST /move, GET /health; wires MCTS + TT
  tt_store.py     TTStore (S3 upload/download) + TTSyncQueue (background backup)

app/        FastAPI application layer — deployed as the app container
  main.py         App factory (create_app), CORS, error handler, lifespan
  config.py       Settings from env vars (DATABASE_URL, JWT_SECRET_KEY, ENGINE_URL, …)
  auth.py         JWT helpers, bcrypt, FastAPI dependencies (get_current_user, Db)
  schemas.py      Pydantic request/response models
  routes/         HTTP route handlers (auth, users, friends, invites, games, moves)
  db/             asyncpg pool + SQL queries (connection.py, queries/, schema.sql)
  game_logic/     Board serialization, UUID tracking (id_map), history, roster
  engine_client.py httpx wrapper for POST /move to the bot service

frontend/   Next.js frontend — dev server via `make frontend`

cpp/        C++ rollout engine (pybind11 bridge)
  engine.cpp    Full rollout hot-loop in C++; exposes run_rollouts() and run_rollout_with_rolls()
  state_codec.py  Python→wire-format encoder consumed by the C++ decoder
tests/      pytest — unit tests per module
scripts/    Standalone utilities (benchmark.py for win-rate validation)
docs/       Design docs, API spec, local testing runbook
```

## Key Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | _(unset — required)_ | App raises `RuntimeError` on startup if missing; set in `.env` or Compose |
| `JWT_SECRET_KEY` | _(unset)_ | JWT signing secret; must be set (≥32 chars) always |
| `BOT_API_SECRET` | _(unset)_ | Shared secret for app→bot auth; must be set (≥32 chars) always |
| `ENGINE_URL` | `http://localhost:5001` | Same locally and in ECS (network_mode=host) |
| `ENVIRONMENT` | `production` | Set to `development` in `.env` for local dev (disables Secure cookie, enables OpenAPI docs) |
| `POKECHESS_TT_BUCKET` | _(unset)_ | S3 bucket for TT backups; omit to disable |
| `POKECHESS_TT_SIZE` | `1048576` | TT slot count; use `67108864` in prod |
| `TRUSTED_PROXY_IPS` | `*` | IPs/CIDRs trusted for `X-Forwarded-For` (rate-limit key source). Must be set to the ALB/VPC CIDR in production (e.g. `10.0.0.0/16`); app raises `RuntimeError` if `*` outside development. |
| `REGISTRATION_ACCESS_CODE` | _(unset — optional)_ | **Temporary pre-launch gate.** When set, `POST /auth/register` returns 403 unless the request body includes a matching `access_code`. Leave unset for open registration. Will be removed before public launch. |

## Make Targets

| Command | What it does |
|---|---|
| `make partial` | Start postgres, wait healthy, apply schema (PvP only) |
| `make full` | `docker compose up --build` all 3 services + schema (PvP + PvB) |
| `make app` | Run uvicorn app on :8000 (foreground) |
| `make frontend` | Run Next.js dev server on :3000 (foreground) |
| `make schema` | Apply `app/db/schema.sql` |
| `make bot-id` | Print seeded Metallic bot UUID |
| `make test` | Run pytest |
| `make test-v` | Run pytest verbose |
| `make down` | `docker compose down` (keeps volume) |
| `make reset` | `docker compose down -v` (wipes DB volume) |

## Key Design Decisions

**Algorithm:** Pure MCTS (no neural network for MVP). No training needed — runs at inference time. Time budget per move (default 3s) controls difficulty. Tree is reused between moves: when the bot plays move A and the opponent responds X, the A→X subtree is retained as the new root.

**Stochasticity:** Pokeball captures are coin flips (50%). `apply_move()` returns a list of `(state, probability)` pairs — usually one pair at p=1.0, two pairs for pokeball interactions. MCTS samples these during rollouts.

**Inter-game learning:** Transposition table (Zobrist hash → wins/visits) persists across games. Common positions accumulate statistics, giving warm-start priors.

**HP:** Always a multiple of 10. Zobrist hp_bucket = current_hp // 50.

**C++ move ordering:** `get_legal_moves` in C++ iterates the board in row-major order (not the `pieces[]` array). This matches Python's `all_pieces()` board iteration. If you change this to array-index order the fixed-roll tests will fail (different moves selected for the same roll).

## Game Rules Summary

See `docs/Rules.md` and `docs/PieceMovement.pdf` for full rules. Key points:
- Standard chess rules apply except no en passant, no castling
- Red (Pikachu) moves first. Blue (Eevee) moves second.
- Pieces have HP and typed moves. Attacker stays put unless it KOs the target.
- Attack range = movement range for all pieces.
- Type matchups: Water > Fire > Grass > Water (2x/1x/0.5x). Same type = 0.5x.
- Mew (Queen, Psychic, 250HP) has 4 moves and can always one-shot any starter.
- Eevee (Blue King, Normal, 120HP) can move + attack same turn (Quick Attack).
- Pikachu (Red King, Electric, 200HP) immune to regular pokeballs.
- Kings evolve mid-game: Pikachu→Raichu (costs a turn), Eevee→one of 5 evolutions.
- Foresight (Mew/Espeon): targets a square, resolves on caster's next turn. Can't use consecutively.
