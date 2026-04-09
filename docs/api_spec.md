# PokeChess App — API Specification

**Status:** Proposed — see open decisions and **App — open questions** in `implementation_roadmap.md` before implementing  
**Last updated:** April 2026

Cross-reference: `docs/pokechess_data_model.md` for all JSONB shapes, table schemas, and the move lifecycle flow.

---

## Overview

### Base URL
- Production: `https://api.pokechess.app` (TBD)
- Local dev: `http://localhost:8000`

### Authentication
JWT Bearer tokens. Include in every authenticated request:
```
Authorization: Bearer <access_token>
```
Tokens are short-lived (suggested: 30 min). A refresh token (longer-lived, httpOnly cookie) is used to obtain new access tokens without re-login.

### Versioning
No versioning prefix for v1 (`/games/{id}`, not `/v1/games/{id}`). Add prefix when a breaking change is required.

### Error response format
```json
{
  "error": "move_not_legal",
  "detail": "The submitted move is not in the legal move set for this position."
}
```

### Open decision: response envelope
All endpoints below return bare objects (no outer `{data: ..., meta: ...}` wrapper). Revisit if pagination becomes complex.

---

## Auth Endpoints

### `POST /auth/register`
No auth required.

**Request:**
```json
{
  "username": "ash",
  "email": "ash@example.com",
  "password": "..."
}
```

**Response `201`:**
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user_id": "uuid"
}
```

---

### `POST /auth/login`
No auth required.

**Request:**
```json
{
  "email": "ash@example.com",
  "password": "..."
}
```

**Response `200`:**
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user_id": "uuid"
}
```

---

### `POST /auth/refresh`
Requires valid refresh token (httpOnly cookie). Returns a new access token.

**Response `200`:**
```json
{ "access_token": "...", "token_type": "bearer" }
```

---

## User Endpoints

### `GET /me`
Auth required. Returns the authenticated user's profile and persistent pieces.

**Response `200`:**
```json
{
  "id": "uuid",
  "username": "ash",
  "email": "ash@example.com",
  "created_at": "2026-04-01T00:00:00Z",
  "pieces": [
    {
      "id": "uuid",
      "role": "king",
      "species": "pikachu",
      "xp": 0,
      "evolution_stage": 0
    }
  ]
}
```
`pieces` is the user’s persistent roster from `pokemon_pieces` (see `pokechess_data_model.md`). The collection can grow over time; array length is not fixed. The example shows one object; responses include every owned piece.

---

### `PATCH /me/settings`
Auth required.

**Request (partial update — send only changed fields):**
```json
{
  "board_theme": "forest",
  "extra_settings": { "sound_enabled": false }
}
```

**Response `200`:** updated settings object.

---

## Friends (PvP — may be deferred to v2)

### `GET /friends`
Auth required. Returns accepted friends and pending requests.

**Response `200`:**
```json
{
  "friends": [{ "user_id": "uuid", "username": "misty" }],
  "incoming": [{ "id": "uuid", "from_user_id": "uuid", "username": "brock" }],
  "outgoing": [{ "id": "uuid", "to_user_id": "uuid", "username": "gary" }]
}
```

---

### `POST /friends`
Auth required. Send a friend request.

**Request:**
```json
{ "username": "misty" }
```

**Response `201`:**
```json
{ "id": "uuid", "status": "pending" }
```

---

### `PUT /friends/{id}`
Auth required. Accept or reject an incoming request.

**Request:**
```json
{ "action": "accept" }   // or "reject"
```

**Response `200`:**
```json
{ "id": "uuid", "status": "accepted" }
```

---

## Game Invites (PvP — may be deferred to v2)

The invite flow: sender creates an invite → a pending `games` row is created simultaneously → recipient accepts → game becomes active.

### `GET /game-invites`
Auth required. Returns pending invites addressed to the authenticated user.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "from_user_id": "uuid",
    "from_username": "misty",
    "game_id": "uuid",
    "created_at": "..."
  }
]
```

---

### `POST /game-invites`
Auth required. Challenge a friend to a PvP game.

**Request:**
```json
{ "invitee_id": "uuid" }
```
Server creates the `game_invites` row and a `games` row with `status='pending'`. The inviter is always assigned Red (moves first) — **open decision: should the inviter choose color?**

**Response `201`:**
```json
{
  "invite_id": "uuid",
  "game_id": "uuid",
  "status": "pending"
}
```

**Errors:**
- `409` if an active game already exists between this pair (`one_active_pvp` unique index)
- `404` if invitee not a friend

---

### `PUT /game-invites/{id}`
Auth required (invitee only). Accept or reject.

**Request:**
```json
{ "action": "accept" }   // or "reject"
```

**Response `200`:**
```json
{
  "invite_id": "uuid",
  "status": "accepted",
  "game_id": "uuid"
}
```
On `accept`: `games.status` transitions to `'active'`, `games.whose_turn` set to `'red'`.

---

## Game Endpoints

### `GET /games`
Auth required. Returns active and recently completed games for the authenticated user.

**Response `200`:**
```json
{
  "active": [ ...GameSummary objects... ],
  "completed": [ ...GameSummary objects (last 10)... ]
}
```

**GameSummary object** (no JSONB — fast query, real columns only):
```json
{
  "id": "uuid",
  "status": "active",
  "whose_turn": "red",
  "turn_number": 14,
  "is_bot_game": true,
  "bot_side": "blue",
  "red_player_id": "uuid",
  "blue_player_id": null,
  "winner": null,
  "updated_at": "..."
}
```

---

### `POST /games`
Auth required. Create a PvB game directly (no invite flow).

**Request:**
```json
{
  "bot_id": "uuid",
  "player_side": "red"
}
```
`player_side` is `"red"` or `"blue"`. The bot occupies the other side. **Open decision: should this be randomized if omitted?**

Server:
1. Creates `pokemon_pieces` rows (5 per user) if this is the user's first game
2. Builds `GameState.new_game()`, injects piece UUIDs from `pokemon_pieces`
3. Creates `games` row + `game_pokemon_map` rows

**Response `201`:** full GameDetail object (see `GET /games/{id}`).

---

### `GET /games/{id}`
Auth required (must be a participant). Returns full game state for rendering.

**Response `200` — GameDetail object:**
```json
{
  "id": "uuid",
  "status": "active",
  "whose_turn": "red",
  "turn_number": 14,
  "is_bot_game": true,
  "bot_side": "blue",
  "red_player_id": "uuid",
  "blue_player_id": null,
  "winner": null,
  "end_reason": null,
  "state": { ...GameState.to_dict() output... },
  "move_history": [ ...move history entries... ]
}
```

`state` is the full `games.state` JSONB — see `pokechess_data_model.md` for the complete shape.  
`move_history` is the full `games.move_history` JSONB array — included for animation, last-move highlighting, and Foresight display.

**Open decision:** Should `move_history` be a separate endpoint (`GET /games/{id}/history`) to allow the polling loop to skip it when only checking turn state? At 5–20 users the TOAST overhead is negligible, but a `?include=history` query param is a low-cost future option.

---

### `POST /games/{id}/resign`
Auth required (active participant only).

**Request:** empty body.

**Response `200`:** GameDetail with `status: "complete"`, `winner` set to the opponent, `end_reason: "resign"`.

---

## Move Endpoints

### `GET /games/{id}/legal_moves`
Auth required. Returns all legal moves for the piece at the given square, for the active player.

**Query params:** `piece_row` (int, 0–7), `piece_col` (int, 0–7)

**Response `200`:**
```json
[
  {
    "piece_row": 7,
    "piece_col": 4,
    "action_type": "MOVE",
    "target_row": 6,
    "target_col": 4,
    "secondary_row": null,
    "secondary_col": null,
    "move_slot": null
  },
  {
    "piece_row": 7,
    "piece_col": 4,
    "action_type": "QUICK_ATTACK",
    "target_row": 6,
    "target_col": 5,
    "secondary_row": 5,
    "secondary_col": 5,
    "move_slot": null
  },
  {
    "piece_row": 7,
    "piece_col": 4,
    "action_type": "QUICK_ATTACK",
    "target_row": 6,
    "target_col": 5,
    "secondary_row": 5,
    "secondary_col": 4,
    "move_slot": null
  }
]
```

**`action_type` values** use engine `ActionType` enum names (uppercase): `"MOVE"`, `"ATTACK"`, `"FORESIGHT"`, `"TRADE"`, `"EVOLVE"`, `"QUICK_ATTACK"`, `"RELEASE"`.

These strings are different from `move_history.action_type` values (lowercase, semantic). The app server handles the mapping when writing history.

**Frontend notes:**
- For most pieces: one Move object per target square.
- **Mew targeting an enemy:** up to 3 Move objects for the same `(target_row, target_col)` — one per `move_slot` (0=Fire Blast/Fire, 1=Hydro Pump/Water, 2=Solar Beam/Grass). Additionally, FORESIGHT Move objects will appear for that square (and others). The frontend must present a picker when multiple moves share a target square. See open decisions.
- **Espeon targeting an enemy:** 2 Move objects for the same square — one `ATTACK` (direct, no slot) and one `FORESIGHT`. Same disambiguation needed.
- **Eevee QUICK_ATTACK:** multiple Move objects share the same `(target_row, target_col)` but have different `(secondary_row, secondary_col)`. Frontend must first select the attack target, then show available secondary destinations. See open decisions.
- **Eevee EVOLVE:** exactly 0 or 1 EVOLVE move — determined by held item. No picker needed; just a button.

**Errors:**
- `400` if it is not the requesting player's turn
- `404` if no piece exists at the given square

---

### `POST /games/{id}/move`
Auth required (must be the active player). Submit a move.

**Request** — the full Move object as returned by `GET /games/{id}/legal_moves`:
```json
{
  "piece_row": 7,
  "piece_col": 4,
  "action_type": "QUICK_ATTACK",
  "target_row": 6,
  "target_col": 5,
  "secondary_row": 5,
  "secondary_col": 5,
  "move_slot": null
}
```
Null fields may be omitted. `action_type` must be an engine ActionType enum name (uppercase).

**Server behavior** (see Move Lifecycle Flow in `pokechess_data_model.md`):
1. Validates move is in `get_legal_moves(state)`
2. Applies the move via `apply_move()`; resolves stochastic Pokéball outcomes and records `rng_roll`
3. Detects and records Foresight resolution if it occurred this turn
4. Checks `is_terminal()` — sets status/winner if game over
5. PvB only, if not over: calls `POST localhost:5001/move` on the engine container, applies the bot's response
6. Writes updated state, history, and turn columns to Postgres in a single `UPDATE`
7. On game over: writes XP to `game_pokemon_map` and `pokemon_pieces`

**Response `200`:** full GameDetail object (same shape as `GET /games/{id}`), reflecting the state after both the human move and (for PvB) the bot's response.

**Open decision:** If the bot move takes close to `time_budget` seconds (up to 3s), this endpoint blocks for that duration. This is acceptable for v1. SSE or a polling model for bot response is a v2 option.

**Errors:**
- `400 move_not_legal` — submitted move not found in `get_legal_moves(state)`
- `400 not_your_turn` — `games.whose_turn` does not match the authenticated user's team
- `409 game_not_active` — game is not in `status='active'`

---

## Notes on the `whose_turn` column

`games.whose_turn` stores lowercase `'red'` or `'blue'` (SQL `CHECK` constraint). The `games.state` JSONB stores `"active_player": "RED"` or `"BLUE"` (uppercase, matching the Python `Team` enum). The app server must lowercase `active_player` when writing the `whose_turn` column after each move.

---

## Not covered here

- Password reset / email verification (add before launch)
- Admin endpoints
- Rate limiting (add at the infrastructure/gateway layer)
- The engine's internal `POST /move` and `POST /backup` endpoints (see `docs/app_and_engine_communication.md`)
