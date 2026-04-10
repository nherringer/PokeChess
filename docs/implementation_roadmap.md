# PokeChess — Architecture & Implementation Roadmap

**Status:** Scaffolding complete, implementation in progress  
**Last updated:** April 2026

---

## Agreed Architecture

### Repo structure — monorepo, two Dockerfiles

```
pokechess/                      ← single repo (rename from PokeChess-engine → pokechess)
  engine/                       ← shared game logic; imported by BOTH containers  ✓ exists
    state.py                    ← GameState, Piece, enums, PIECE_STATS
    moves.py                    ← get_legal_moves(), Move, ActionType
    rules.py                    ← apply_move(), is_terminal(), hp_winner()
    zobrist.py                  ← Zobrist hashing (engine container only in practice)
  bot/                          ← MCTS bot; engine container only  ✓ exists
    mcts.py
    ucb.py
    transposition.py
  cpp/                          ← C++ rollout extension; engine container only  ✓ exists
    engine.cpp
    state_codec.py              ← binary wire format for C++ bridge
  app/                          ← FastAPI app server; app container only  ✓ scaffolded
    README.md                   ← pointer to data model + roadmap docs
    main.py                     ← TODO
    routes/                     ← TODO
    db/                         ← TODO
  tests/                        ← ✓ exists (engine/bot tests only so far)
  docs/                         ← ✓ exists
  Dockerfile.engine             ← ✓ created (needs bot/server.py to be runnable)
  Dockerfile.app                ← ✓ created (needs app/main.py to be runnable)
  docker-compose.yml            ← ✓ created
```

The dependency arrow is one-way: `bot/` and `app/` both import `engine/`; `engine/` imports neither. No code is duplicated. CI/CD builds two images from one repo on every merge to main.

**Rename note:** The repo is currently named `PokeChess-engine`. Rename to `pokechess` before setting up CI/CD — the name is misleading now that `app/` lives here too.

### Container responsibilities

| Concern | Container | How |
|---|---|---|
| Move validation | `pokechess-app` | `get_legal_moves(state)` from `engine/` |
| Move application | `pokechess-app` | `apply_move(state, move)` from `engine/` |
| Terminal detection | `pokechess-app` | `is_terminal(state)` from `engine/` |
| Legal move serving (frontend) | `pokechess-app` | `get_legal_moves()`, filtered by piece |
| MCTS bot move selection | `pokechess-engine` | `MCTS.select_move(state)` via `POST /move` |
| State persistence | `pokechess-app` | Postgres JSONB via `GameState.to_dict()` / `from_dict()` |
| XP attribution | `pokechess-app` | Reads `move_history`, writes `game_pokemon_map` + `pokemon_pieces` |

The engine container is called **only for PvB games, only to get the bot's move**. It is stateless with respect to game logic. The app applies every move (human and bot) itself.

### Engine API contract (`POST localhost:5001/move`)

**Request:**
```json
{
  "state": { ...GameState.to_dict() output... },
  "time_budget": 1.0
}
```

**Response:**
```json
{
  "piece_row": 0, "piece_col": 3,
  "action_type": "ATTACK",
  "target_row": 1, "target_col": 4,
  "secondary_row": null, "secondary_col": null,
  "move_slot": null
}
```

The engine deserializes the state, runs MCTS, returns the best move. It does not apply the move or return a new state. The app applies the move using `apply_move()`.

---

## State & History Format (canonical)

### `games.state` JSONB

Output of `GameState.to_dict()`. Fields:

- `active_player`: `"RED"` or `"BLUE"` (matches `Team` enum name)
- `turn_number`: int
- `has_traded`: `{"RED": bool, "BLUE": bool}` — required for cold resume
- `foresight_used_last_turn`: `{"RED": bool, "BLUE": bool}` — required for cold resume
- `pending_foresight`: `{"RED": effect|null, "BLUE": effect|null}` — effect has `target_row`, `target_col`, `damage`, `resolves_on_turn`
- `board`: flat array of on-board pieces only (captured pieces are removed and not tracked)

Each piece in `board`:
- `id`: UUID string (from `pokemon_pieces.id`) for named pieces; `null` for pawns
- `piece_type`: engine `PieceType` enum name (e.g. `"SQUIRTLE"`, `"RAICHU"`)
- `team`: `"RED"` or `"BLUE"`
- `row`, `col`: int 0–7 (row 0 = Red's back rank)
- `current_hp`: int (0 for Safetyballs/Pokéballs)
- `held_item`: engine `Item` enum name (e.g. `"WATERSTONE"`, `"NONE"`)
- `stored_piece`: inline nested piece object or `null`

### `games.move_history` JSONB

Append-only array. All coordinates are row/col integers. `player` is `"RED"` or `"BLUE"`.

| `action_type` | Engine source | Key result fields |
|---|---|---|
| `move` | `ActionType.MOVE` | `{}` normally; `stored: true, stored_piece_id, stored_hp, stored_max_hp` when Safetyball stores an ally |
| `attack` | `ActionType.ATTACK` (named piece) | `damage, type_multiplier, target_hp_before, target_hp_after, captured` |
| `pokeball_attack` | `ActionType.ATTACK` (Pokéball) | `rng_roll, captured, pokeball_spent` |
| `masterball_attack` | `ActionType.ATTACK` (Masterball) | `captured: true, pokeball_spent: true` |
| `quick_attack` | `ActionType.QUICK_ATTACK` | `damage, type_multiplier, target_hp_before, target_hp_after, captured`; uses `attack_to_row/col` + `move_to_row/col` |
| `release` | `ActionType.RELEASE` | `released_piece_id, released_hp` |
| `evolve` | `ActionType.EVOLVE` | `from_species, to_species, hp_restored` |
| `foresight` | `ActionType.FORESIGHT` | `target_row, target_col, damage, resolves_on_turn` |
| `foresight_resolve` | *(app-injected, turn start)* | `target_row, target_col, damage, target_piece_id, target_hp_before, target_hp_after, captured` |
| `trade` | `ActionType.TRADE` | `item_given, item_received, triggered_evolution, evolved_to` |

See `docs/pokechess_data_model.md` for full JSON examples.

---

## Next Steps by Team

### ML Engineer

**Blocking (unblocks everything else):**

1. **Add `id: Optional[str] = None` to `Piece` dataclass** (`engine/state.py:116`)  
   One line. The engine never reads it; it is carried opaquely through `copy()` and `apply_move()`. Named pieces get UUIDs injected by the app server at game creation.

2. **Add `to_dict()` / `from_dict()` to `Piece`, `ForesightEffect`, and `GameState`** (`engine/state.py`)  
   Implement the JSON codec described in `docs/PokeChess Notation Design...pdf` (Primitive 1). The output shape must match the `games.state` spec in `pokechess_data_model.md`. Include `has_traded`, `foresight_used_last_turn`, and `damage` in the foresight effect.  
   Estimated: 2–3 hours. Add round-trip tests in `tests/test_state.py`.

3. **Write `engine/notation.py`** (PokeChess-PGN, Primitive 2 from the notation PDF)  
   `move_to_str()`, `str_to_move()`, `GameRecord` class. Used for replay/analysis; not needed for Postgres storage. Can be done in parallel with app work once FEN is done.  
   Estimated: 4–6 hours.

**Engine container:**

4. ~~**Write `Dockerfile.engine`**~~ ✓ Done — see `Dockerfile.engine` at repo root. Includes optional C++ extension build with pure-Python fallback. Blocked on `bot/server.py`.

5. **Write `bot/server.py`** — FastAPI wrapper around `MCTS.select_move()`  
   `POST /move`: deserializes state via `GameState.from_dict()`, runs MCTS, returns the best move as JSON.  
   `POST /backup`: triggers transposition table serialization to S3.  
   Estimated: 2–3 hours.

6. **Wire `iteration_budget` into `MCTS.select_move()`** (currently only `time_budget` is implemented)  
   Optional for v1 but listed in `bots.params` spec.

---

### App Backend Engineer

*Depends on: ML engineer completing items 1 and 2 above.*

1. ~~**Create `app/` directory structure**~~ ✓ Done — `app/` scaffolded with `README.md`. See `app/README.md` for the intended layout and key import patterns.

2. ~~**Write `Dockerfile.app`**~~ ✓ Done — see `Dockerfile.app` at repo root.

3. ~~**Write `docker-compose.yml`**~~ ✓ Done — see `docker-compose.yml` at repo root. Add `SECRET_KEY` and S3 env vars before first run with real data.

4. **Write DB migrations** for the full schema in `pokechess_data_model.md`  
   All tables: `users`, `user_settings`, `friendships`, `bots`, `game_invites`, `games`, `pokemon_pieces`, `game_pokemon_map`.  
   Seed one default bot row in `bots` (name: **Metallic**, representing Team Alpha's artificial intelligence).

5. **Auth endpoints** (`POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`)  
   JWT access token (short-lived) + httpOnly refresh token cookie. See `docs/api_spec.md`.

6. **Friends endpoints** (`GET /friends`, `POST /friends`, `PUT /friends/{id}`) — **required for v1 (PvP is in scope)**  
   Friend request flow: send → pending → accept/reject. See `docs/api_spec.md`.

7. **Game invite endpoints** (`GET /game-invites`, `POST /game-invites`, `PUT /game-invites/{id}`) — **required for v1**  
   Creating an invite also creates a `games` row with `status='pending'`. Accepting transitions game to `status='active'`. See `docs/api_spec.md`.

8. **Game creation endpoint** (`POST /games`) — PvB only (no invite flow)  
   - Create `pokemon_pieces` rows if this is the user's first game (full roster — one per named piece, not a fixed 5)
   - Serialize `GameState.new_game()` via `to_dict()`, injecting piece UUIDs from `pokemon_pieces`  
   - Write `games` row + `game_pokemon_map` rows  

9. **Legal moves endpoint** (`GET /games/{id}/legal_moves?piece_row=&piece_col=`)  
   Deserialize state, call `get_legal_moves()`, filter for the requested piece, return the full Move field set for each legal move: `piece_row`, `piece_col`, `action_type` (engine enum name), `target_row`, `target_col`, `secondary_row`, `secondary_col`, `move_slot`. The frontend uses these objects verbatim as the `POST /move` payload — `secondary_row`/`col` are needed for Quick Attack, `move_slot` for Mew's attack types and Eevee's evolution choices.

10. **Move submission endpoint** (`POST /games/{id}/move`)  
    Full lifecycle: deserialize → validate → apply → detect Foresight resolution → build history entry → check terminal → PvB: call engine → write back. Returns full GameDetail after both plies (human + bot) for PvB. See Move Lifecycle Flow in `pokechess_data_model.md`.

11. **XP attribution on game completion**  
    Use the isolated `compute_xp(move_history) → dict[piece_id, int]` helper (XP = damage dealt per piece). Write `game_pokemon_map` and `pokemon_pieces` rows. See Q5 resolved above.

---

### App Frontend Engineer

*Depends on: app backend completing items 3–5 above.*

1. **Board rendering from `games.state`**  
   Deserialize the `board[]` array. Each piece has `piece_type`, `team`, `row`, `col`, `current_hp`, `held_item`. Convert `(row, col)` → algebraic notation for display if needed. Render stored pieces with a visual indicator on the Safetyball square (check `stored_piece` field).

2. **Legal move highlighting**  
   On piece click: call `GET /games/{id}/legal_moves?piece_row=&piece_col=`. Highlight returned target squares by action_type (different visual for move vs attack vs foresight vs trade). Note: for a single target square there may be multiple legal moves with different `move_slot` values (e.g. Mew targeting one square with Fire Blast, Hydro Pump, or Solar Beam). The UI needs to handle this — see open questions.

3. **Move submission**  
   On target selection: `POST /games/{id}/move` with the full Move object received from the legal moves endpoint. The payload is `{piece_row, piece_col, action_type, target_row, target_col, secondary_row, secondary_col, move_slot}`. For most moves most optional fields are null. For Quick Attack, `secondary_row`/`col` are the post-attack destination. For Mew attacks and Eevee evolution, `move_slot` encodes the choice.

4. **Game polling**  
   Poll `GET /games/{id}` on the game view (1–3s interval). Update board when `turn_number` changes or `status` becomes `'complete'`. Fetch the full `state` JSONB for rendering.

5. **Stochastic outcome display**  
   Pokéball throws: animate/display the `rng_roll` outcome from the latest `move_history` entry. The result is already resolved server-side; frontend just reads `captured: true/false`.

6. **Foresight UI**  
   Show the pending Foresight target square from `pending_foresight` in the state. When a `foresight_resolve` entry appears in history, show the damage landing.

7. **TODO (post-v1):** Client-side move input validation to prevent obviously illegal submissions. Server already validates; this is a UX improvement.

---

## App — open questions (product & API)

These decisions block or complicate frontend, backend, or sequencing if left unspecified. Cross-check **`docs/api_spec.md`** first: some former gaps (e.g. `GET /games/{id}` and `POST /games/{id}/move` returning a **GameDetail** envelope with `state` and `move_history`) are already spelled out there; optional extras like `?include=history` remain called out in the spec as open.

### Q1. Mew and multi-option move UI (frontend)

For a single target square, **Mew** can yield up to three distinct legal moves (attack slots / move types). **Eevee evolution** can yield up to five moves when evolving via stone. The legal-moves API can return multiple `Move` objects that share the same target; the UI must disambiguate (modal, picker step, or a different selection flow) before calling `POST /games/{id}/move`.

**✅ Resolved:** Bottom-sheet picker slides up ~200px from the bottom of the board on ambiguous target selection. Mew shows up to 4 options (3 attack slots + Foresight as a move option). Eevee evolution shows 5 evolution sprites with name + type badge. See `docs/frontend_layout_proposal.md` for full UX detail.

### Q2. PvP scope: invites, friends, and roadmap alignment

The data model includes `game_invites`, friends flows, and a pending → active game transition. The **backend checklist** in this doc currently emphasized **PvB** (`POST /games`) and did not enumerate invite/friends endpoints.

**✅ Resolved — PvP is in scope for v1. Play vs Friend is a hard requirement.**  
`GET/POST /friends`, `GET/POST/PATCH /game-invites`, and the pending → active game transition must all ship in v1. The app backend checklist below has been updated accordingly. See `docs/api_spec.md` for the full endpoint contracts.

### Q3. `POST /games/{id}/move` response (polling vs. single payload)

For PvB, the server may apply the human move and then the bot move before responding; latency can approach the engine’s time budget (up to 10s at Master difficulty).

**Specified in `docs/api_spec.md`:** response `200` returns a full **GameDetail** (same shape as `GET /games/{id}`) after both plies when applicable.

**✅ Resolved — single GameDetail payload is the v1 contract.**  
The frontend displays a **"Metallic is thinking…"** state (spinning Pokeball, board grayed out) for the duration of the wait. Metallic is the name of the PvB bot, representing Team Alpha’s artificial intelligence. The single-response contract avoids polling complexity while the wait state keeps the UX clear. If latency requirements change in future, the thin-response + poll pattern can be introduced without breaking the frontend contract.

### Q4. `GET /games/{id}` payload options

**Specified in `docs/api_spec.md`:** GameDetail includes `state`, `move_history`, terminal fields, and metadata.

**✅ Resolved — legal moves remain a separate endpoint. `GET /games/{id}` never embeds them.**  
The extra round-trip for `GET /games/{id}/legal_moves` is acceptable; the performance impact at this scale is negligible. A clean separation between game state and move computation is worth more than the saved request. No query flags (e.g. `?include=legal_moves`) will be added. The `GET /games` list endpoint returns GameSummary objects (no JSONB) as already specified.

### Q5. XP earning formula

`xp_earned` vs `xp_applied` appears in the data model, but the rule for **what events** (per move, per game, damage-based, etc.) populate `xp_earned` is undefined.

**✅ Resolved (v1) — XP earned = total damage dealt by that piece during the game.**  
Each attack move in `move_history` that includes a `damage` field contributes that amount to `xp_earned` for the attacking piece. Pokeball captures (no damage field) do not contribute. Foresight damage uses the `damage` field in its `foresight_resolve` entry.

Implementation note: XP attribution should be computed in a single pass over `move_history` at game end. Keep the attribution logic in an isolated helper function (e.g. `compute_xp(move_history) → dict[piece_id, int]`) so the formula can be changed without touching the game flow. The formula is explicitly expected to evolve — do not hardcode it into the game-end handler.

### Q6. `pokemon_pieces.species` updates for mid-game evolution

If **Eevee** (or similar) evolves during a game, engine state and `move_history` reflect it, but updating **`pokemon_pieces.species` only at game completion** means an abandoned game leaves the roster row out of sync with history.

**✅ Resolved — Kings (Pikachu and Eevee) are in-game-only evolutions and are never persisted as evolved forms.**

- Every new game always starts with **Pikachu** (Red King) and **Eevee** (Blue King) — never Raichu or any Eevee evolution. Their mid-game evolved forms are transient engine state only.
- `pokemon_pieces.species` for king and queen pieces is **immutable** — `'pikachu'`, `'eevee'`, or `'mew'`, never updated. Mew has no evolution. King mid-game evolutions are transient engine state only.
- `pokemon_pieces.evolution_stage` does **not apply** to kings or the queen (always 0). They are exempt from the XP-threshold evolution system.
- Kings and queen still have `pokemon_pieces` rows and accumulate `xp_earned` in `game_pokemon_map` (XP = damage dealt). This XP is tracked but never triggers persistent evolution.
- Only rooks, knights, and bishops have mutable `species` and a meaningful `evolution_stage`. Their evolutions happen post-game only, so the Q6 timing problem (abandoned game leaving species out of sync mid-game) does not apply to any piece — no incremental update is needed.

### Minor implementation notes (no separate decision)

- **Pokéball RNG:** Prefer selecting stochastic branches with explicit probabilities (e.g. `random.choices` with weights) rather than assuming ordering of `apply_move` outcome tuples.
- **`whose_turn` vs state:** DB column is lowercase `red`/`blue`; `games.state.active_player` is uppercase — normalize when writing columns (`docs/api_spec.md`).
- **App route code:** When building `Move` from JSON, use engine types (`Move`, `ActionType`) and compare against `get_legal_moves()` — see `app/README.md` imports; extend as needed for deserialization helpers.

---

## Key Constraints & Risks

| Risk | Mitigation |
|---|---|
| Engine `to_dict()` / `from_dict()` round-trip has a bug | Add comprehensive tests: mid-game states with stored pieces, pending Foresight, held items, both flags true |
| Piece UUID injection at game creation drifts from `pokemon_pieces` rows | Write a test that creates a game, extracts piece IDs from state, and verifies they match `game_pokemon_map.pokemon_piece_id` |
| `foresight_resolve` entry missed (Foresight fires but no history entry written) | Unit test: play a game through Foresight resolution, assert history has a `foresight_resolve` entry with correct turn/damage |
| Pokéball RNG: app and engine see different random outcomes | RNG happens on the app side only; engine returns a move, never an outcome. No divergence possible. |
| Engine container unavailable in PvP game | PvP games never call the engine container. Only PvB games are affected by engine downtime. |
