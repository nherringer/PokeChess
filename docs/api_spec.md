# PokeChess — HTTP API specification (app backend)

This document describes the **public HTTP API** of the FastAPI app (`pokechess-app`): authentication, request/response bodies, **status codes**, **error shapes**, query parameters, and behavioral notes that are not obvious from Pydantic class definitions alone.

**Canonical sources (keep in sync):**

| Concern | Location |
|--------|----------|
| Route handlers, business rules, side effects | `app/routes/` (`auth.py`, `users.py`, `friends.py`, `invites.py`, `games.py`, `moves.py`, `bots.py`), `app/main.py` (`/health`) |
| Pydantic models (field names and types) | `app/schemas.py` |
| High-level overview + product context | [MASTERDOC.md](MASTERDOC.md) §5 |
| `games.state` / `games.move_history` JSON shapes | [pokechess_data_model.md](pokechess_data_model.md) |
| Runtime machine-readable schema | OpenAPI: `GET /openapi.json` and Swagger UI `GET /docs` when the server is running |

**Base URL:** Depends on deployment (e.g. `http://localhost:8000`). All API paths below are **absolute** from the app root.

**Content type:** `application/json` for request and response bodies unless noted.

---

## 1. Authentication

### 1.1 Access token (JWT)

- **Header:** `Authorization: Bearer <access_token>`
- **Algorithm / claims:** `HS256`; payload includes `sub` (user UUID string), `exp`, `type: "access"` — see `app/auth.py`.
- **Required on:** Every route except `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /health`, and `GET /bots` (public bot catalog).

If the header is missing or invalid, FastAPI’s `HTTPBearer` dependency typically yields **403**; invalid/expired JWT decoding raises **`AppError`** → **401** with JSON body (see §2).

### 1.2 Refresh token (cookie)

- **Cookie name:** `refresh_token`
- **Set by:** `POST /auth/register`, `POST /auth/login` (HttpOnly, `SameSite=Lax`, `Secure` when `ENVIRONMENT` is not `development`).
- **Used by:** `POST /auth/refresh` reads this cookie (no Bearer header required for refresh).

### 1.3 Config (environment)

Relevant variables: `JWT_SECRET_KEY`, `BOT_API_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ENVIRONMENT`, `CORS_ORIGINS`, `TRUSTED_PROXY_IPS` — see `app/config.py`. **Temporary pre-launch:** `REGISTRATION_ACCESS_CODE` gates `POST /auth/register` when set; see §3.2 and §5.4 of MASTERDOC for details and removal plan.

---

## 2. Error responses

### 2.1 Application errors (`AppError`)

Many failures use a unified JSON body:

```json
{
  "error": "<short_code>",
  "detail": "<human-readable message>"
}
```

**HTTP status** equals the code passed to `AppError` (e.g. 400, 401, 403, 404, 409, 503). Common `error` string values include: `conflict`, `unauthorized`, `forbidden`, `not_found`, `bad_request`, `game_not_active`, `not_your_turn`, `illegal_move`, `engine_error`, `engine_unavailable`, etc. — see `app/routes/*.py` and `app/auth.py`.

### 2.2 Validation errors (Pydantic / FastAPI)

Malformed JSON or invalid field types typically produce **422 Unprocessable Entity** with FastAPI’s default validation error shape (`detail` array).

### 2.3 Server errors

Unexpected internal failures may return **500** without the `AppError` shape.

---

## 3. Endpoint reference

### 3.1 Health (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness. **Response:** `200` — `{"status": "ok"}` |

### 3.2 Auth

| Method | Path | Auth | Request body | Success response |
|--------|------|------|--------------|------------------|
| `POST` | `/auth/register` | None | `RegisterRequest` | **201** `TokenResponse` |
| `POST` | `/auth/login` | None | `LoginRequest` | **200** `TokenResponse` |
| `POST` | `/auth/refresh` | Cookie `refresh_token` | None | **200** `RefreshResponse` |

**`TokenResponse` fields:** `access_token`, `token_type` (default `"bearer"`), `user_id`.

**`RefreshResponse` fields:** `access_token`, `token_type` (default `"bearer"`). (No `user_id` in the body — clients should retain it from `TokenResponse` or fetch `GET /users/me` after refresh.)

**Cookies on register/login:** Sets `refresh_token` as described in §1.2.

**Rate limiting:** Auth routes use **SlowAPI** with per-client-IP limits (`app/routes/auth.py`): `POST /auth/register` **3/minute**, `POST /auth/login` **10/minute**, `POST /auth/refresh` **20/minute**. When exceeded, the response is **429 Too Many Requests** (SlowAPI default error body).

**Temporary pre-launch registration gate:** `RegisterRequest` includes an optional `access_code: string | null` field. When the `REGISTRATION_ACCESS_CODE` environment variable is set, the server checks this field on `POST /auth/register` and returns **403** if it is missing or wrong. When `REGISTRATION_ACCESS_CODE` is unset (default), the field is ignored and registration is open. This gate will be removed before public launch.

**Typical errors:**

| Condition | Status | Notes |
|-----------|--------|--------|
| Duplicate username/email on register | 409 | `conflict` |
| Bad login credentials | 401 | `unauthorized` |
| Missing/invalid refresh cookie or token | 401 | `unauthorized` |
| Rate limit exceeded (auth routes) | 429 | SlowAPI |
| Invalid or absent `access_code` on register (when `REGISTRATION_ACCESS_CODE` set) | 403 | `forbidden` — temporary pre-launch gate |

---

### 3.3 Current user & settings

User routes are mounted under the **`/users`** prefix (`app/routes/users.py`). All routes in this subsection require **Bearer** access token.

| Method | Path | Request body | Success response |
|--------|------|--------------|------------------|
| `GET` | `/users/me` | — | **200** `UserProfile` |
| `POST` | `/users/me/starter` | — | **201** `StarterResponse` |
| `PATCH` | `/users/me/settings` | `SettingsUpdate` | **200** `SettingsOut` |

**`UserProfile`:** `id`, `username`, `email`, `created_at`, `pieces` (list of `PieceOut`).

**`PieceOut`:** `id`, `role`, `species`, `set_side` (`"red"` or `"blue"`), `xp`, `evolution_stage`.

**`StarterResponse`:** `pieces` (list of `PieceOut`). **Idempotent** — if the user already has roster rows, returns existing pieces with **201**.

**`SettingsUpdate`:** optional `board_theme`, optional `extra_settings` (object; must serialize to JSON, max **16 384** bytes serialized, max nesting depth **8** — validated in `schemas.py`).

**`SettingsOut`:** `board_theme`, `extra_settings`, `updated_at`.

**Typical errors:**

| Condition | Status |
|-----------|--------|
| Settings row missing on PATCH | 404 |

---

### 3.4 Bots (catalog)

**No Bearer token** — public list for difficulty / PvB UI (`app/routes/bots.py`).

| Method | Path | Request body | Success response |
|--------|------|--------------|------------------|
| `GET` | `/bots` | — | **200** JSON array of `BotOut` |

**`BotOut`:** `id`, `name`, `stars` (1–6 difficulty indicator; 6 = METALLIC), `flavor`, `forced_player_side` (`"red" | "blue" | null`), `accent_color` (CSS hex), `trainer_sprite` (filename), `time_budget` (seconds; from `bots.params`, ordered ascending in the list query; `null` if not set in the row).

---

### 3.5 Friends

Bearer required.

| Method | Path | Request body | Success response |
|--------|------|--------------|------------------|
| `GET` | `/friends` | — | **200** `FriendsResponse` |
| `POST` | `/friends` | `SendFriendRequest` | **201** `FriendActionResponse` |
| `PUT` | `/friends/{friendship_id}` | `FriendActionRequest` | **200** `FriendActionResponse` |

**`SendFriendRequest`:** exactly one of **`username`** or **`email`** (target user).

**`FriendActionRequest`:** `action` — must be **`"accept"`** or **`"reject"`** (otherwise 400).

**`FriendsResponse`:** `friends` (list of `FriendUser`), `incoming` / `outgoing` (lists of `FriendRequest`).

**`FriendActionResponse`:** `id` (friendship UUID), `status`.

**Typical errors:**

| Condition | Status |
|-----------|--------|
| Target user not found | 404 |
| Friend request to self | 400 |
| Duplicate pending request | 409 |
| Friendship not found / not pending / wrong user | 404 / 400 / 403 |

---

### 3.6 Game invites (PvP lobby)

Bearer required.

| Method | Path | Request body | Success response |
|--------|------|--------------|------------------|
| `GET` | `/game-invites` | — | **200** JSON array of `InviteOut` |
| `POST` | `/game-invites` | `SendInviteRequest` | **201** `InviteActionResponse` |
| `PUT` | `/game-invites/{invite_id}` | `InviteActionRequest` | **200** `InviteActionResponse` |
| `DELETE` | `/game-invites/{invite_id}` | — | **200** `InviteActionResponse` (inviter-only cancel) |

**`SendInviteRequest`:** `invitee_id` (UUID), `player_side` — **`"red"`**, **`"blue"`**, or **`"random"`** (inviter's chosen team; `"random"` is resolved to a concrete side at creation time). Invitee must already be an **accepted friend** (otherwise 404 `Invitee is not a friend`).

**`InviteActionRequest`:** `action` — **`"accept"`** or **`"reject"`**.

**`InviteOut`:** `id`, `game_id`, `created_at`, `direction` (`"incoming" | "outgoing"`), `other_user_id`, `other_username`, `inviter_id`, `invitee_id`, `inviter_side` (`"red" | "blue"` — always concrete).

**`InviteActionResponse`:** `invite_id`, `status`, `game_id`.

**Behavior:** `POST` creates a **pending** game row and invite. **Accept** initializes the PvP game state (roster, etc.); **reject** marks invite rejected. **DELETE** lets the inviter withdraw a still-pending invite (status becomes `rejected`).

**Typical errors:**

| Condition | Status |
|-----------|--------|
| Not friends with invitee | 404 |
| Active game already exists between pair | 409 |
| Invite not found / not invitee / not pending | 404 / 403 / 400 |
| `DELETE` by non-inviter / invite not pending | 403 / 400 |

---

### 3.7 Games

Bearer required.

| Method | Path | Request body | Success response |
|--------|------|--------------|------------------|
| `GET` | `/games` | — | **200** `GamesListResponse` |
| `POST` | `/games` | `CreateGameRequest` | **201** `GameDetail` |
| `GET` | `/games/{game_id}` | — | **200** `GameDetail` |
| `POST` | `/games/{game_id}/resign` | — | **200** `GameDetail` |

**`CreateGameRequest`:** `bot_id` (UUID), `player_side` — **`"red"`** or **`"blue"`** only.

- **`POST /games` creates PvB only:** the human occupies `player_side`; the bot occupies the opposite side. **PvP games are not created here** — they come from the invite flow (`POST /game-invites` + accept).

**`GamesListResponse`:** `active`, `completed` — each lists `GameSummary` objects.

**`GameSummary`:** `id`, `status`, `whose_turn`, `turn_number`, `is_bot_game`, `bot_side`, `red_player_id`, `blue_player_id`, `winner`, `updated_at` — **no** heavy `state`/`move_history` JSONB. **List-only (from `GET /games`):** `opponent_display` (other human’s username, or bot name for PvB) and `my_side` (`"red"` / `"blue"` for the authenticated user) so clients can label “vs …” and “your turn” vs “waiting for …”.

**List behavior:** **Completed** games for the user are limited to the **10** most recently updated (`app/db/queries/games.py`). Active games are not capped.

**`GameDetail`:** `id`, `status`, `whose_turn`, `turn_number`, `is_bot_game`, `bot_side`, `red_player_id`, `blue_player_id`, `winner`, `end_reason`, `state`, `move_history`.

- **`state`:** Board snapshot object (see data model doc). May be `null` in edge cases from DB, but normal games have an object.
- **`move_history`:** Array of move history objects (see data model doc). May be empty `[]`.

**`whose_turn`:** Lowercase **`"red"`** / **`"blue"`** in DB/API; in **`state.active_player`** you will see **`RED`** / **`BLUE`** — compare carefully.

**Typical errors:**

| Condition | Status |
|-----------|--------|
| Not a participant | 403 |
| Game not found | 404 |
| `player_side` invalid | 400 |
| Bot not found | 404 |
| Resign when not active | 409 |

---

### 3.8 Moves (legal moves + submit)

Bearer required.

| Method | Path | Query / body | Success response |
|--------|------|----------------|------------------|
| `GET` | `/games/{game_id}/legal_moves` | **Required query:** `piece_row`, `piece_col` (integers **0–7**) | **200** JSON array of `LegalMoveOut` |
| `POST` | `/games/{game_id}/move` | `MovePayload` | **200** `GameDetail` |

**`LegalMoveOut` / `MovePayload` fields:** `piece_row`, `piece_col`, `action_type`, `target_row`, `target_col`, optional `secondary_row`, `secondary_col`, `move_slot`.

**`action_type`:** Must be **`engine.moves.ActionType` enum names** (`MOVE`, `ATTACK`, `FORESIGHT`, `TRADE`, `EVOLVE`, `QUICK_ATTACK`, `RELEASE`) — exactly as returned by `GET .../legal_moves` (see `app/routes/moves.py` / `LegalMoveOut`, which uses `action_type.name`).

**Legal moves:** Only returns moves for the **selected piece** at `(piece_row, piece_col)` that match the current player’s turn. Client must send a **verbatim** `MovePayload` matching one of the returned legal moves (including `move_slot` when disambiguating Mew/Eevee).

**`POST /games/{game_id}/move` behavior:**

1. Validates move against `get_legal_moves(state)`.
2. Applies move; resolves Pokéball RNG on the **server** (not in the engine HTTP service).
3. **PvB:** If the game continues and it becomes the bot’s turn, the app calls the **engine** `POST /move`, applies the bot move, and may append both plies to history before responding — **one** `GameDetail` reflects the post-bot state (and can take up to engine time budget + network).

**Typical errors:**

| Condition | Status | `error` (typical) |
|-----------|--------|-------------------|
| Not participant | 403 | `forbidden` |
| Game not active | 409 | `game_not_active` |
| Not your turn | 409 | `not_your_turn` |
| No friendly piece at square | 400 | `bad_request` |
| Invalid `action_type` | 400 | `bad_request` |
| Move not legal | 400 | `illegal_move` |
| Engine unreachable / HTTP error | 503 | `engine_unavailable` / `engine_error` |

---

## 4. Response models (quick reference)

Names refer to **`app/schemas.py`**.

| Model | Used for |
|-------|----------|
| `RegisterRequest`, `LoginRequest` | Auth request bodies |
| `TokenResponse`, `RefreshResponse` | Auth success |
| `UserProfile`, `PieceOut` | `GET /users/me` |
| `StarterResponse` | `POST /users/me/starter` |
| `SettingsUpdate`, `SettingsOut` | `PATCH /users/me/settings` |
| `BotOut` | `GET /bots` |
| `FriendsResponse`, `SendFriendRequest`, `FriendActionRequest`, `FriendActionResponse` | Friends |
| `SendInviteRequest`, `InviteOut`, `InviteActionRequest`, `InviteActionResponse` | Invites |
| `CreateGameRequest`, `GameSummary`, `GameDetail`, `GamesListResponse` | Games |
| `MovePayload`, `LegalMoveOut` | Moves |

---

## 5. Related: engine service (not this app’s routes)

The **MCTS engine** is a separate process (e.g. port **5001**). The app calls:

- `POST http://<ENGINE_URL>/move` with JSON `{"state": {...}, "persona_params": {"time_budget": <float>, ...}}` — see `app/engine_client.py` and [MASTERDOC.md](MASTERDOC.md) §5.3.

That contract is **not** part of the public REST API exposed to browsers under the same app prefix; document it for **server-to-server** integration only.
