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
   Seed one default bot row in `bots`.

5. **Game creation endpoint** (`POST /games`)  
   - Create `pokemon_pieces` rows if first game (5 per user)  
   - Serialize `GameState.new_game()` via `to_dict()`, injecting piece UUIDs from `pokemon_pieces`  
   - Write `games` row + `game_pokemon_map` rows  

6. **Legal moves endpoint** (`GET /games/{id}/legal_moves?piece_row=&piece_col=`)  
   Deserialize state, call `get_legal_moves()`, filter for the requested piece, return the full Move field set for each legal move: `piece_row`, `piece_col`, `action_type` (engine enum name), `target_row`, `target_col`, `secondary_row`, `secondary_col`, `move_slot`. The frontend uses these objects verbatim as the `POST /move` payload — `secondary_row`/`col` are needed for Quick Attack, `move_slot` for Mew's 3 attack types and Eevee's 5 evolution choices.

7. **Move submission endpoint** (`POST /games/{id}/move`)  
   Full lifecycle: deserialize → validate → apply → detect Foresight resolution → build history entry → check terminal → PvB: call engine → write back. See Move Lifecycle Flow in `pokechess_data_model.md`.

8. **XP attribution on game completion**  
   Tally `xp_earned` from `move_history` per piece. Apply win/loss rule. Write `game_pokemon_map` and `pokemon_pieces` rows.

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

## Key Constraints & Risks

| Risk | Mitigation |
|---|---|
| Engine `to_dict()` / `from_dict()` round-trip has a bug | Add comprehensive tests: mid-game states with stored pieces, pending Foresight, held items, both flags true |
| Piece UUID injection at game creation drifts from `pokemon_pieces` rows | Write a test that creates a game, extracts piece IDs from state, and verifies they match `game_pokemon_map.pokemon_piece_id` |
| `foresight_resolve` entry missed (Foresight fires but no history entry written) | Unit test: play a game through Foresight resolution, assert history has a `foresight_resolve` entry with correct turn/damage |
| Pokéball RNG: app and engine see different random outcomes | RNG happens on the app side only; engine returns a move, never an outcome. No divergence possible. |
| Engine container unavailable in PvP game | PvP games never call the engine container. Only PvB games are affected by engine downtime. |
