# PokeChess — Master documentation

**Purpose:** This document is the **primary reference** for the PokeChess codebase and product: how the monorepo is organized, how requests and game state flow through the system, what the HTTP API exposes, how data is stored, how the bot and load-aware budgeting work, what the planned frontend must do, and how target deployment fits. Other files under `docs/` add depth (full SQL, exhaustive JSON examples, game rules prose, UX mockups). **If you read one file, read this one**; use the links when you need the full detail of a subsystem.

**Last updated:** 17 April 2026

---

## How to use this document

| If you need… | Start here | Then open… |
|--------------|------------|------------|
| Big picture + contracts | Sections 2–5 below | Same document (no other file required) |
| Full HTTP API (methods, status codes, errors, auth) | — | [api_spec.md](api_spec.md), `app/routes/`, `app/schemas.py` |
| Exact Pydantic/DB shapes | Sections 5.1–5.2 | `app/schemas.py`, [pokechess_data_model.md](pokechess_data_model.md) |
| DDL and indexes | Section 6 | `app/db/schema.sql`, [pokechess_data_model.md](pokechess_data_model.md) |
| Chess/Pokémon rules | Section 7 | [Rules.md](Rules.md) |
| UI/UX for a future client | Section 8 | [frontend_layout_proposal.md](frontend_layout_proposal.md) |
| AWS/ECS target | Section 10 | [architecture_design_plan.md](architecture_design_plan.md) |
| ML bot / roadmap tasks | Section 9 | [implementation_roadmap.md](implementation_roadmap.md) |

---

## 1. TL;DR

- **Game:** Two-player strategy on an 8×8 board. Chess-like movement, but pieces have **HP**, **Pokémon types**, **items**, and **abilities**. **RED** (Pikachu king) moves first; **BLUE** (Eevee king) second. Win by eliminating the opponent’s king (see [Rules.md](Rules.md)).
- **Modes:** **PvP** — two human accounts (friends + game invites). **PvB** — one human vs one of **six bot personalities** (Bonnie → METALLIC, Kalos-themed difficulty tiers); the app calls a separate **engine** service only for the bot’s move choice.
- **Code:** **One monorepo**: `engine/` (pure rules), `app/` (FastAPI + Postgres), `bot/` + `cpp/` (MCTS + optional C++ rollout in the engine image). **Two Docker images** (`Dockerfile.app`, `Dockerfile.engine`) built from the same repo.
- **Truth for HTTP:** **[api_spec.md](api_spec.md)** (methods, bodies, status codes, errors); **`app/schemas.py`** (Pydantic field types); **`app/routes/`** (handler behavior); **[pokechess_data_model.md](pokechess_data_model.md)** (`games.state` / `move_history` JSON). At runtime, **`/openapi.json`** and **`/docs`** (Swagger UI).
- **Local dev:** `docker-compose.yml` + env (`DATABASE_URL`, `ENGINE_URL`, `JWT_SECRET_KEY`, etc.). **Target production:** two ECS services on one small EC2 instance ([architecture_design_plan.md](architecture_design_plan.md)).
- **Engine HTTP container:** `bot/server.py` exists and is functional. `Dockerfile.engine` wires to `uvicorn bot.server:app`. The engine image builds and runs. PvB bot moves are unblocked end-to-end — see [implementation_roadmap.md](implementation_roadmap.md) for remaining polish items.

---

## 2. Repository layout (monorepo)

### 2.1 Why a monorepo

Game rules live in **one** Python package (`engine/`). Both the app server and the bot **import** that package. Splitting into separate repositories would duplicate `engine/` or force a versioned package; a single repo keeps **one source of truth** and lets CI produce **two images** from one commit.

### 2.2 Dependency rule

```
engine/     ← no imports from app/ or bot/
app/        ← imports engine/
bot/        ← imports engine/
```

### 2.3 Directory tree (conceptual)

```
pokechess/                    ← single repo (may still be named PokeChess-engine in git)
  engine/
    state.py                  # GameState, Piece, enums, PIECE_STATS
    moves.py                  # get_legal_moves(), Move, ActionType
    rules.py                  # apply_move(), is_terminal(), hp_winner()
    zobrist.py                # transposition hashing (engine-side search)
  bot/
    mcts.py, ucb.py, transposition.py
    # bot/server.py — FastAPI HTTP wrapper; POST /move + GET /health
  cpp/                        # optional C++ rollout; pybind11 bridge
  app/
    main.py                   # FastAPI, lifespan, DB pool, httpx engine client
    routes/                   # auth, users, friends, invites, games, moves
    db/                       # schema.sql, asyncpg queries
    game_logic/               # serialization, XP, roster helpers
    engine_client.py          # POST to engine /move
  tests/
  docs/
  Dockerfile.app
  Dockerfile.engine
  docker-compose.yml
```

**Rename note:** The repo may still be named `PokeChess-engine`; renaming to something like `pokechess` before CI/CD reduces confusion now that `app/` exists ([implementation_roadmap.md](implementation_roadmap.md)).

### 2.4 Container responsibilities

| Concern | Where it runs | Mechanism |
|---------|----------------|-----------|
| Validate moves | App | `get_legal_moves(state)` from `engine/` |
| Apply moves (human + bot) | App | `apply_move()` from `engine/` |
| Terminal / winner | App | `is_terminal()` from `engine/` |
| Expose legal moves to client | App | Filter `get_legal_moves()` by piece |
| Choose bot move | Engine container | MCTS `select_move` → returns a move; **does not** apply it or touch Postgres |
| Persist state | App | Postgres JSONB + columns |
| XP at game end | App | Scan `move_history`, update `game_pokemon_map` / `pokemon_pieces` |

The **engine container is stateless for game rules**: it receives a state dict, searches, returns a move JSON. **Only PvB** games invoke it, and **only** when it is the bot’s turn.

---

## 3. Product snapshot

### 3.1 PvP flow (high level)

1. Users register / log in (`/auth/*`).
2. They become friends (`/friends/*`).
3. One user sends a **game invite** (`POST /game-invites`); server creates a **pending** game row and invite.
4. Invitee **accepts** (`PUT /game-invites/{id}`) → game becomes **active**; both players play via `GET/POST /games/*` and moves.

### 3.2 PvB flow

1. Human creates a game with a **bot_id** and side (`POST /games`) — roadmap and schemas define the exact body.
2. Six **bot personas** are seeded in `bots` (see `app/db/schema.sql` and [bot_personas.md](bot_personas.md)): **Bonnie** (easiest), **Team Rocket**, **Serena**, **Clemont**, **Diantha**, **METALLIC** (hardest).
3. Each bot row’s **`params` JSONB** carries its full MCTS configuration (`time_budget`, `exploration_c`, `use_transposition`, and optionally `move_bias` + `bias_bonus`). These are forwarded as `persona_params` to the engine on every move request — see Section 5.3.
4. After each human move the app commits the human ply and returns a `GameDetail` immediately (reflecting only the human move). If it is then the bot’s turn, a **background task** calls the engine `POST /move` and writes the bot ply asynchronously. The client detects the bot’s turn via `whose_turn == bot_side` and polls at a faster interval (1 s) until the game state updates; if the bot move has not arrived after 15 s the client calls `POST /games/{id}/retry-bot-move` to re-queue it (idempotent).

### 3.3 Persistent roster (“My Pokémon”)

Each user owns **named** pieces (king, queen, rooks, knights, bishops) stored in `pokemon_pieces`. **Pawns** (Stealballs, Safetyballs, Pokéballs) are **not** roster rows — they are ephemeral on the board. XP and evolution rules interact with **rook/knight/bishop** pieces post-game; kings and Mew have special rules (Section 6.4).

### 3.4 Client application

A **Next.js** client lives under **`frontend/`** on this branch (local development; not necessarily production-deployed). It uses the same polling pattern the API was designed for (`GET /games/{id}` on a 2.5 s interval during the human's turn, switching to 1 s while `whose_turn == bot_side`) and the REST contracts below. [frontend_layout_proposal.md](frontend_layout_proposal.md) remains the **v1 UX specification** (tablet/phone-first, dark Pokémon-inspired UI); the implementation may lag or diverge in details.

### 3.5 Future: solo campaign

[CampaignDesign.md](CampaignDesign.md) describes exploratory **solo campaign** ideas — **not** part of the current build or backend scope.

---

## 4. Runtime architecture

### 4.1 Core services diagram

```mermaid
flowchart LR
  subgraph clients [Clients]
    Browser[Browser]
  end
  subgraph app [pokechess_app]
    Core["FastAPI + shared<br/>engine library"]
  end
  DB[(PostgreSQL)]
  subgraph engineSvc [pokechess_engine]
    Bot[MCTS bot]
  end
  Browser -->|REST polling| Core
  Core --> DB
  Core -->|POST /move PvB only| Bot
```

### 4.2 Load-aware PvB: many humans, one bot personality

When several people play **PvB** against the **same** bot row (e.g. Metallic) at once, the app **does not** give every game the full `time_budget` from `bots.params`. It records each human’s last move in **`bot_player_activity`**, counts how many distinct players are **active** in a sliding time window (`BOT_ACTIVE_WINDOW_MINUTES`), sets **effective_time_budget = base_time_budget / N**, and passes that value in **`persona_params.time_budget`** to the engine. Details: Section 9.2 and [load_aware_budgeting.md](load_aware_budgeting.md).

The diagram is intentionally **linear top-to-bottom**: each step follows the previous; only the **bottom** node is the outbound call to the engine.

```mermaid
flowchart TB
  subgraph concurrent [Concurrent PvB games same bot_id]
    G1[Human player A]
    G2[Human player B]
    G3[Human player C]
  end
  App[FastAPI app]
  Upsert[Upsert last_moved_at]
  BPA[(bot_player_activity)]
  CountN[COUNT gives N in window]
  Budget[persona_params time_budget = base / N]
  Eng[Engine POST /move]
  G1 -->|submit move| App
  G2 -->|submit move| App
  G3 -->|submit move| App
  App --> Upsert
  Upsert --> BPA
  BPA --> CountN
  CountN --> Budget
  Budget --> Eng
```

### 4.3 Human move path (simplified)

1. Client sends `POST /games/{game_id}/move` with a move matching a legal move from `GET /games/{game_id}/legal_moves`.
2. App loads the row from `games`, checks auth and `whose_turn`, deserializes `state` to `GameState`.
3. App verifies the move is in `get_legal_moves(state)`.
4. App runs `apply_move` (handles Pokéball RNG on the **app** side — engine never rolls RNG for captures).
5. App may inject **foresight_resolve** history entries when a pending Foresight fires.
6. If PvB and bot’s turn next: app calls **engine** `POST /move` with serialized state and `persona_params` (including load-adjusted `time_budget`), parses flat move JSON, validates against legal moves, applies bot move.
7. App writes updated `state`, appended `move_history`, `whose_turn`, `turn_number`, `status`, `winner`, `end_reason` as appropriate; on terminal, runs XP logic.

### 4.4 Polling and payloads

- **`GET /games/{id}`** returns **GameDetail**: metadata plus **`state`** and **`move_history`** JSON for rendering. It does **not** embed legal moves: use **`GET /games/{id}/legal_moves`** (implemented). Roadmap Q4 only ruled out bundling legal moves into `GET /games/{id}` — not whether the legal-moves route exists.
- **`GET /games/{id}/legal_moves?piece_row=&piece_col=`** returns the list of legal **Move** shapes for that piece; the client submits one of those verbatim to `POST /games/{id}/move`.
- **`whose_turn`** in the DB uses lowercase `red` / `blue`; **`games.state.active_player`** uses uppercase `RED` / `BLUE` — normalize when comparing.

### 4.5 Serialization

Wire format for DB and engine requests is owned by the app: **`app/game_logic/serialization.py`** (`state_to_dict` / `state_from_dict` or equivalent) aligned with [pokechess_data_model.md](pokechess_data_model.md). Engine **dataclasses** in `engine/state.py` stay free of JSON methods; the app is the codec boundary.

---

## 5. Contracts

### 5.1 HTTP API surface (implemented routes)

All routes are mounted from `app/main.py`. Prefixes below are **full path prefixes**. For **request/response contracts, auth, and error codes**, see **[api_spec.md](api_spec.md)**; for **Pydantic types**, see **`app/schemas.py`**; for **handler logic**, see **`app/routes/`**.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/auth/register` | Create user, default settings, return access token; sets httpOnly refresh cookie |
| `POST` | `/auth/login` | Login; tokens + refresh cookie |
| `POST` | `/auth/refresh` | New access token from refresh cookie |
| `GET` | `/users/me` | Authenticated user profile + pieces |
| `POST` | `/users/me/starter` | Idempotent “claim starter roster” (returns pieces; register/login also seeds roster when empty) |
| `PATCH` | `/users/me/settings` | User settings (`board_theme`, `extra_settings` JSONB with API validation) |
| `GET` | `/bots` | List bot personalities (`BotOut`: id, name, stars, flavor, `forced_player_side`, `accent_color`, `trainer_sprite`, `time_budget`) — **no Bearer required** |
| `GET` | `/friends` | Friends + incoming/outgoing friend requests |
| `POST` | `/friends` | Send friend request by username |
| `PUT` | `/friends/{friendship_id}` | Accept or reject (`action` in body) |
| `GET` | `/game-invites` | Pending invites |
| `POST` | `/game-invites` | Create invite + pending game (must be friends); body: `invitee_id`, `player_side` (`"red"`/`"blue"`/`"random"`) |
| `PUT` | `/game-invites/{invite_id}` | Accept/reject invite |
| `DELETE` | `/game-invites/{invite_id}` | Inviter-only cancel of a pending invite |
| `GET` | `/games` | Active + completed lists (**GameSummary** — no heavy JSONB). Includes **`opponent_display`** and **`my_side`** for UI copy (vs opponent / whose turn). **Completed** list is capped at **10** rows (most recently updated); active games are not capped (`app/db/queries/games.py`). |
| `POST` | `/games` | Create **PvB** game only — body requires `bot_id` and `player_side` (`CreateGameRequest`). **PvP** games are created via **`POST /game-invites`** (pending row + invite), then activated on accept — not via this endpoint. |
| `GET` | `/games/{game_id}` | **GameDetail** — full `state` + `move_history` |
| `POST` | `/games/{game_id}/resign` | Resign |
| `GET` | `/games/{game_id}/legal_moves` | Legal moves for one piece |
| `POST` | `/games/{game_id}/move` | Submit move; **GameDetail** response (may include bot ply in PvB) |
| `GET` | `/health` | Liveness |

**Authoritative types:** `app/schemas.py` (`RegisterRequest`, `GameDetail`, `MovePayload`, `LegalMoveOut`, etc.). **Authoritative HTTP contract (status codes + errors):** [api_spec.md](api_spec.md).

### 5.2 Auth model (summary)

- **Access token:** JWT in `Authorization: Bearer` for API calls.
- **Refresh token:** HttpOnly cookie (`refresh_token`) on register/login; `/auth/refresh` rotates access.
- **Config:** `JWT_SECRET_KEY`, `BOT_API_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ENVIRONMENT`, `CORS_ORIGINS`, `TRUSTED_PROXY_IPS` — see `app/config.py`. `JWT_SECRET_KEY` and `BOT_API_SECRET` must always be set (≥ 32 chars); the app raises `RuntimeError` at startup if either is missing.
- **Rate limiting (app):** **SlowAPI** in `app/main.py` applies per-client-IP limits on auth routes in `app/routes/auth.py`: `POST /auth/register` **3/minute**, `POST /auth/login` **10/minute**, `POST /auth/refresh` **20/minute**. When exceeded, responses are **429**; clients should back off. **`TRUSTED_PROXY_IPS` must be restricted to the ALB/VPC CIDR in production**; leaving it as `*` lets clients spoof `X-Forwarded-For` and land each attempt in a fresh rate-limit bucket. **Reverse-proxy** or **WAF** limits in front of the app remain a good extra layer; app limits are not a substitute for volumetric DDoS protection.
- **Registration password:** `RegisterRequest` enforces a minimum password length (**8** characters) via Pydantic — see `app/schemas.py`.

### 5.3 Engine `POST /move` — **code is canonical**

The app calls the engine over HTTP (`app/engine_client.py`). **`POST /move`** must include header **`X-Bot-Api-Secret`** with the same value as **`BOT_API_SECRET`** in config; **`bot/server.py`** compares it to the engine process’s **`BOT_API_SECRET`** (constant-time) and returns **401** if missing or wrong. **`GET /health`** is **not** authenticated — for liveness only. App and engine containers must share one secret (e.g. identical env in compose or matching secrets in ECS).

JSON body:

```json
{
  "state": { "...": "GameState wire dict" },
  "persona_params": {
    "time_budget": 1.5,
    "exploration_c": 1.4142135623730951,
    "use_transposition": true,
    "move_bias": "chase_pikachu",
    "bias_bonus": 0.15
  }
}
```

`time_budget` is **seconds**, possibly **divided by N** active players for load-aware budgeting (Section 9.2). All numeric persona params are **clamped** by the engine before use (`time_budget` to `[0.1, 10.0]`, `exploration_c` to `[0.05, 10.0]`, `bias_bonus` to `[0.0, 3.0]`). `move_bias` and `bias_bonus` are optional — only sent for personas with behavioral biases (Team Rocket, Clemont). See [bot_personas.md](bot_personas.md) for the full parameter table.

The engine must return a **flat** JSON object the app can pass into `Move(...)`:

- `piece_row`, `piece_col`, `action_type` (engine enum **name**, e.g. `"ATTACK"`)
- `target_row`, `target_col`
- `secondary_row`, `secondary_col` (e.g. Quick Attack)
- `move_slot` (Mew / Eevee evolution disambiguation)

**Note:** [implementation_roadmap.md](implementation_roadmap.md) §Engine API shows `time_budget` at the **top level** of the JSON; the **running app** nests it under `persona_params`. When implementing `bot/server.py`, accept the **app’s** shape.

### 5.4 Environment variables (app)

| Variable | Role |
|----------|------|
| `DATABASE_URL` | AsyncPG DSN (see `config.asyncpg_dsn()`) |
| `ENGINE_URL` | Base URL for engine (default `http://localhost:5001`) |
| `JWT_SECRET_KEY` | JWT signing — required, ≥ 32 chars |
| `BOT_API_SECRET` | Same value on app and engine; app sends `X-Bot-Api-Secret` on `POST /move` — required, ≥ 32 chars |
| `ENVIRONMENT` | `development` vs `production` checks (defaults to `production`) |
| `CORS_ORIGINS` | Comma-separated origins — required, no wildcard default |
| `BOT_ACTIVE_WINDOW_MINUTES` | Sliding window for load-aware bot budgeting (default 22) |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes |
| `TRUSTED_PROXY_IPS` | IPs/CIDRs trusted for `X-Forwarded-For` (rate-limit key source). Must be ALB/VPC CIDR in production (e.g. `10.0.0.0/16`); app raises `RuntimeError` if `*` outside development. |
| `REGISTRATION_ACCESS_CODE` | **Temporary pre-launch gate.** When set, `POST /auth/register` returns 403 unless the request body includes a matching `access_code`. Leave unset for open registration. Will be removed before public launch. |

**`.env.example` and Compose:** The repo **`.env.example`** lists `DATABASE_URL` and `ENGINE_URL` so the full app surface is visible. For **`docker compose`**, **`docker-compose.yml`** still sets `DATABASE_URL` and `ENGINE_URL` on `pokechess-app` (from `POSTGRES_*` and service names), so you can leave those lines empty in `.env` when using Compose only. For **production** (e.g. ECS) or **running the app without Compose**, set `DATABASE_URL` to your Postgres DSN and `ENGINE_URL` to the engine base URL as needed.

---

## 6. Data model (concise reference)

**Full DDL and examples:** `app/db/schema.sql` and [pokechess_data_model.md](pokechess_data_model.md).

**Production DB and schema changes:** There is **no Alembic** (or other migration runner) in this repo — see [implementation_roadmap.md](implementation_roadmap.md). **New** databases: apply **`app/db/schema.sql`** once (e.g. `psql $DATABASE_URL -f app/db/schema.sql`). **Existing** production or staging databases must be upgraded with **manual** `ALTER TABLE` / data backfill steps whenever `schema.sql` changes; plan upgrades by diffing the file against your live DDL. Optional future work: versioned migrations — not required for the current codebase.

### 6.1 Core tables

- **`users`** — Identity: username, email, password hash.
- **`user_settings`** — 1:1 with users; `board_theme`, `extra_settings` JSONB for flexible client prefs.
- **`friendships`** — Ordered pair (`user_a_id` < `user_b_id`), status pending/accepted/rejected, initiator tracked.
- **`bots`** — Bot personality rows; **`params` JSONB** holds MCTS knobs (`time_budget`, `exploration_c`, `use_transposition`, optional `move_bias` + `bias_bonus`). Six personas are seeded: Bonnie, Team Rocket, Serena, Clemont, Diantha, METALLIC. See [bot_personas.md](bot_personas.md) and `bot/persona.py`.
- **`game_invites`** — Inviter, invitee, status; ties to games created in pending state.
- **`games`** — Players (nullable slot for bot side), `is_bot_game`, `bot_id`, `bot_side`, `invite_id`, **`status`** (`pending` / `active` / `complete`), **`whose_turn`**, **`turn_number`**, **`state`** JSONB, **`move_history`** JSONB, **`winner`**, **`end_reason`**. Frequently queried fields are real columns, not buried only in JSONB.
- **`pokemon_pieces`** — Persistent named pieces per user: role, species, xp, evolution_stage.
- **`game_pokemon_map`** — Links pieces to a game; **`xp_earned`**, **`xp_applied`**, **`xp_skip_reason`**, **`xp_applied_at`** for idempotent post-game rollup.
- **`bot_player_activity`** — `(player_id, bot_id)` last move time for load-aware budgeting.

### 6.2 `games.state` JSONB (shape)

Canonical snapshot of the board — output of the app’s state serialization aligned with engine semantics:

- `active_player`: `"RED"` | `"BLUE"`
- `turn_number`: int
- `has_traded`, `foresight_used_last_turn`: per-team bool maps
- `pending_foresight`: per-team null or effect (`target_row/col`, `damage`, `resolves_on_turn`)
- `board`: array of **on-board** pieces only (captured pieces are removed)

Each piece object includes: `id` (UUID string or `null` for pawns), `piece_type`, `team`, `row`, `col`, `current_hp`, `held_item`, nested `stored_piece` for Safetyball contents.

### 6.3 `games.move_history` JSONB

Append-only list of turns. **Snake_case `action_type`** strings in history (`attack`, `pokeball_attack`, `foresight_resolve`, …) differ from **engine enum names** in API moves (`ATTACK`, …) — the app maps between them. See the table in [implementation_roadmap.md](implementation_roadmap.md) or [pokechess_data_model.md](pokechess_data_model.md).

### 6.4 XP and evolution (v1 rules)

- **XP earned (v1):** Sum of **`damage`** from `move_history` entries attributed to that **named** piece (attacks, foresight resolve, etc.). Pokéball captures without damage do not add XP. Implemented in a dedicated helper (e.g. `compute_xp`) so the formula can change.
- **`xp_earned` vs `xp_applied`:** Raw earned vs what business rules apply to `pokemon_pieces.xp` (e.g. wins only — see data model).
- **Kings / queen:** `pokemon_pieces.species` for king and queen is **immutable** (`PIKACHU`, `EEVEE`, `MEW` — stored uppercase to match the engine's `PieceType` enum member names). Mid-game evolutions (Raichu, Eeveelutions) exist **only** in engine state for that game. **Rooks, knights, bishops** can change species/evolution stage **post-game** via XP thresholds; those updates happen at game completion, not mid-game ([implementation_roadmap.md](implementation_roadmap.md) Q6).

### 6.5 Important indexes

- One **active** PvP game per unordered player pair (unique partial index).
- One **active** PvB game per human + bot (unique partial index).
- `bot_player_activity` indexed by `(bot_id, last_moved_at)` for counting active players.

---

## 7. Game rules (overview)

**Authoritative text:** [Rules.md](Rules.md).

**Condensed overview:**

- **Board:** 8×8; RED rows 0–1, BLUE rows 6–7.
- **Back rank:** Squirtle, Charmander, Bulbasaur, King (Pikachu/Eevee), Mew, mirrored.
- **Pawns:** Stealballs and Safetyballs with distinct columns; special capture and storage rules in [Rules.md](Rules.md).
- **Combat:** Moving onto an enemy attacks; damage uses **types** and multipliers. HP to zero removes the piece.
- **Items & trading:** Stone evolutions, held items, adjacent trade action — full detail in rules doc.
- **Pokéballs / Masterballs:** Capture mechanics with RNG (resolved on **app** when applying moves).
- **Win:** Eliminate opponent king — [Rules.md](Rules.md) §11.

---

## 8. Frontend specification (planned client)

**Source:** [frontend_layout_proposal.md](frontend_layout_proposal.md). **Status:** UX spec + reference layout; a **Next.js app** under **`frontend/`** implements much of the flow on active branches (see §3.4). Treat the proposal as the design target, not a line-by-line match to the current UI.

**Audience / platform:** Roughly 8–15 years old; **tablet and phone** primary (portrait primary, landscape secondary).

**Visual language:** Dark-field Pokémon aesthetic (`bg-deep` ~`#12141E`), team reds/blues, Gen-1 sprite art, board as hero. Rounded bold fonts (e.g. Nunito, Fredoka One). Highlight tokens for select / move / attack / foresight / trade.

**Key screens:**

1. **Home** — Play vs Bot, Play vs Friend, My Pokémon, Settings.
2. **My Pokémon** — Scrollable roster cards (species, type, XP bar, held item); read-only v1.
3. **Difficulty (PvB)** — Easy → Master mapping to **0.5s–10.0s** `time_budget`; flavour copy for Metallic.
4. **Lobby** — Creating game or waiting on invite acceptance (share code, cancel).
5. **Gameplay** — 8×8 board, team banners, HP, legal highlights by action type, bottom sheet for **Mew** multi-attack and **Eevee** evolution choice, **Metallic is thinking…** state during long engine waits, Pokeball shake animation using history `rng_roll` / `captured`, Foresight cyan overlay + resolve feedback, Quick Attack two-step selection.
6. **Game over** — Winner by team, XP earned per piece; evolution progress for pieces that evolve via XP (not kings/queen per Q6).

**Design principles (samples):** No algebraic notation required for kids; ambiguous moves use a **bottom sheet**; PvB wait up to **10s** on Master — UI must show clear loading/grayout ([frontend_layout_proposal.md](frontend_layout_proposal.md) resolved decisions table).

---

## 9. Bot, MCTS, load-aware budgeting, and roadmap

### 9.1 MCTS engine container

- **Bot code:** `bot/mcts.py`, `bot/server.py` (FastAPI), `bot/transposition.py` (fixed-size array TT), `bot/tt_store.py` (S3 backup), `bot/persona.py` (six canonical persona definitions); optional **C++** rollout in `cpp/` for speed.
- **Persona system:** `bot/persona.py` defines a `Persona` dataclass and six instances. Each exposes `to_bot_params()` which produces the dict stored in `bots.params` (same numeric values as the seed `INSERT`s in `app/db/schema.sql` and the tables in [bot_personas.md](bot_personas.md)). The engine's `PersonaParams` model reads `time_budget`, `exploration_c`, `use_transposition`, `move_bias`, and `bias_bonus`. A **UCB1 bias bonus** is added to matching child nodes on every selection pass for `chase_pikachu` (Team Rocket) and `prefer_pikachu_raichu` (Clemont) — see [bot_personas.md](bot_personas.md).
- **HTTP surface (repo state):** `bot/server.py` implements `POST /move` and `GET /health`. The engine image builds and runs. App calls it via `app/engine_client.py`.
- **Persistence:** There is **no** app-triggered **`POST /backup`** or app-orchestrated engine backup. The transposition table is stored as a local `.bin` file inside the engine container and optionally backed up to S3 (`POKECHESS_TT_BUCKET`). The app has no visibility into TT state — see [Transposition_Table_Sync.md](Transposition_Table_Sync.md).
- **Future:** `engine/notation.py` for PokeChess-PGN replay/analysis (not required for Postgres).

### 9.2 Load-aware budgeting (implemented in app)

See **Section 4.2** for a diagram of multiple PvB players sharing one bot personality.

Problem: many humans vs the same bot concurrently would each get the full `time_budget` → too much total search time.

**Mechanism:**

1. On each human move in PvB, **upsert** `bot_player_activity` for `(player_id, bot_id)`.
2. Before calling the engine, **count** distinct players with `last_moved_at` in the last **`BOT_ACTIVE_WINDOW_MINUTES`** minutes for that `bot_id`.
3. **effective_time_budget = base_time_budget / N** where `base_time_budget` comes from `bots.params->time_budget` (difficulty). Pass result in `persona_params["time_budget"]`.

The engine does not need separate code paths — it just receives a smaller `time_budget`. See [load_aware_budgeting.md](load_aware_budgeting.md) for SQL and examples.

### 9.3 Roadmap pointer

**Open work, priorities, ML vs app tasks:** [implementation_roadmap.md](implementation_roadmap.md) §Next Steps. **Historical ML notes:** [task_log.md](task_log.md).

---

## 10. Infrastructure and deployment (target)

This is the **intended** production shape, not a guarantee about your current laptop setup.

- **Repo:** Monorepo builds **two** images → push to **ECR** → **ECS** on a single **EC2 t4g.small** (cost estimates in [architecture_design_plan.md](architecture_design_plan.md)).
- **Services:** `pokechess-app` (public HTTP, port 8000), `pokechess-engine` (internal, port 5001, not exposed publicly). On the **same EC2 host**, the app calls the engine at **`ENGINE_URL`** (typically **`http://localhost:5001`**, matching [`app/engine_client.py`](../app/engine_client.py) and compose).
- **Browser → app:** HTTP polling (or SSE later); latency on the order of seconds is acceptable.
- **App → engine:** **`POST /move` only** — payload `{ "state", "persona_params" }` per `engine_client.py`. **No** app-triggered backup endpoint; bot-side TT persistence (in-memory array + local `.bin` + optional S3) stays inside the engine process — see `docs/Transposition_Table_Sync.md`.
- **DB:** **Amazon RDS (PostgreSQL)** for **all** app tables — the FastAPI app is the only service using `DATABASE_URL` / RDS. The engine **does not** connect to RDS.
- **Frontend assets:** React/Next on S3 + CloudFront when a client exists (static assets only; unrelated to engine TT storage).
- **Concurrency / queue:** The engine target is a **queue**: **one MCTS search at a time** per instance, with requests waiting when busy — [architecture_design_plan.md](architecture_design_plan.md). Pair with load-aware **`time_budget`** scaling in the app ([load_aware_budgeting.md](load_aware_budgeting.md)).

**Deferred (v2):** Dedicated compute for engine, start/stop on demand ([architecture_design_plan.md](architecture_design_plan.md)).

---

## 11. Documentation map

| Document | Role |
|----------|------|
| [MASTERDOC.md](MASTERDOC.md) | **This file** — unified reference |
| [api_spec.md](api_spec.md) | **App HTTP API** — methods, bodies, status codes, errors (complements `app/schemas.py` + `app/routes/`) |
| [implementation_roadmap.md](implementation_roadmap.md) | Monorepo checklist, container duties, state/history tables, Q&A decisions, next steps |
| [pokechess_data_model.md](pokechess_data_model.md) | Full schema, JSON examples, HTTP model tables, detailed move lifecycle |
| [architecture_design_plan.md](architecture_design_plan.md) | Target AWS/ECS/EC2/cost/queue narrative |
| [app_and_engine_communication.md](app_and_engine_communication.md) | App ↔ engine contract, RDS vs bot-local persistence, queue model — aligned with **`engine_client.py`** |
| [bot_personas.md](bot_personas.md) | Six bot personas — difficulty tiers, parameter tables, UCB1 bias design |
| [load_aware_budgeting.md](load_aware_budgeting.md) | Load-aware MCTS budgeting |
| [frontend_layout_proposal.md](frontend_layout_proposal.md) | v1 UI/UX spec; **`frontend/`** holds the Next.js client (see §3.4, §8) |
| [Rules.md](Rules.md) | Full game rules |
| [CampaignDesign.md](CampaignDesign.md) | **Future** solo campaign — not current build |
| [task_log.md](task_log.md) | Historical ML task log |
| [TT_s3_upload.txt](TT_s3_upload.txt) | Older TT / S3 design notes — may not match current “bot-local persistence” direction; see [architecture_design_plan.md](architecture_design_plan.md) |
| PDFs (optional assets) | Some checkouts include boards/movement/notation PDFs under `docs/`; **this tree may have none** — if missing, they are optional reference art, not required to run the app. |

---

## 12. Documentation freshness

Use **git history** on `docs/` (e.g. `git log -- docs/`) to see what changed recently. Doc updates sometimes land on long-lived integration branches first; **there is no single branch name** that applies in every clone—compare your branch to `main` (or your default) when auditing.

---

## 13. Known gaps and contradictions (for maintainers)

| Topic | Notes |
|-------|--------|
| **Roadmap vs app engine JSON** | Roadmap shows top-level `time_budget`; app uses `persona_params.time_budget` plus additional persona fields (`exploration_c`, `use_transposition`, `move_bias`, `bias_bonus`). |
| **`app_and_engine_communication.md`** | May reference removed files or wrapped move JSON — **use `engine_client.py` + `moves.py`**. |
| **Roadmap vs routes** | Roadmap sometimes says `PATCH` for invites/friends; implementation uses **`PUT`**. |
| **Data model move lifecycle** | One step may mention updating `species` mid-game; Q6 decisions say kings/queen immutable, other pieces post-game — reconcile wording in [pokechess_data_model.md](pokechess_data_model.md) when editing. |
| **Frontend UX copy** | Occasional “~3s” bot wait vs **10s** Master tier — treat **10s** as worst case for UX. |
| **Engine doc typos** | “PvP vs engine” should read **PvB** — engine is never used for human-vs-human. |
| **Engine image ready** | `bot/server.py` implemented; `Dockerfile.engine` builds and runs. |
| **`FOR UPDATE` lock held across engine HTTP** | `POST /games/{id}/move` holds a Postgres row lock for the full engine round-trip (up to `time_budget + 5 s`, max 15 s after the cap was lowered to 10 s). Under concurrent PvB load this risks lock contention and connection pool exhaustion. Fix requires splitting into two transactions (read/validate → release lock → call engine → re-acquire → persist); deferred until pre-production load testing. |

---

## 14. Near-term engineering tasks (pre-production)

Items that are known, scoped, and should be resolved before the service sees real traffic. **Auth routes already have per-IP rate limits** (§5.2); the table below lists **remaining** pre-production gaps. These are not blockers for local development or PvP, but are important before public launch.

| Priority | Task | Detail |
|----------|------|---------|
| **High** | **SES email verification on registration** | Verify new users’ email via **Amazon SES** (or equivalent) before treating the account as fully active or before allowing login. Requires SES identity, templates, and handling bounces/complaints — see AWS SES docs when implementing. |
| **High** | **Persist refresh tokens in the database** | Today refresh tokens are **JWTs** in HttpOnly cookies with no server-side session rows (`app/routes/auth.py` only decodes the JWT and checks the user exists). Store **hashed** refresh token records per device/session to support **revocation**, **rotation**, and **audit** (e.g. logout-all, compromised token). |
| **High** | **Resolve `FOR UPDATE` lock across engine HTTP** | See §13. Splitting `POST /games/{id}/move` into two transactions removes the scalability risk. Requires careful re-validation between transactions to handle concurrent resigns. |
| **Medium** | **Document local testing setup** | One place (e.g. `app/README.md` or a short `docs/` note linked from MASTERDOC) should walk through **local** runs: required env vars (`DATABASE_URL`, `ENGINE_URL`, `JWT_SECRET_KEY`, `BOT_API_SECRET`, `CORS_ORIGINS`, …), bringing up app + engine (e.g. Compose), and **applying `app/db/schema.sql` to Postgres** — `docker compose up` alone does not load the schema, which blocks DB-backed flows until migrations or a manual `psql` apply. Optional: Compose init service or documented one-liner. |

---

## 15. Application README

For a short pointer into the `app/` tree and import conventions, see [app/README.md](../app/README.md).
