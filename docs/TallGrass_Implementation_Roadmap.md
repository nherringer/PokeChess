# TallGrass Update — Implementation Roadmap

**Branch:** `feat/add-tall-grass`  
**Spec:** `docs/TallGrass_Update_Ratified.md`  
**WP groundwork spec:** `docs/WildPokemon_Update_Planned.md` §8  
**Scope:** Full stack. Backend / engine work is the first priority. Frontend (darkened squares, item visibility, overflow UI) is required for the sprint to be considered complete but is implemented after the engine layer is stable.

---

## Goal

Deliver four related mechanical changes in one sprint:

1. **Tall Grass / Item Discovery** — Replace static item initialization with a hidden exploration mechanic. No piece starts the game holding any item. Four items are hidden in the middle rows of the board. Players explore to find them.
2. **Variable Pokeball Catch Rates** — Replace the fixed 50% catch rate with HP-based probabilities that differ between Mew and all other targets.
3. **HP Normalization and Eeveelution Improvements** — Update per-piece HP values, give all eeveelutions Quick Attack retention, add Flareon's 150-damage fire attack, and add Leafeon's passive damage reduction.
4. **Healball Rule Changes** — Restrict Healball entry to injured Pokemon only, permit forward entry by the Pokemon (not just Healball collection), and change Master Healball to instantly restore full HP on entry.

---

## Success Criteria

The implementation is complete when all of the following hold:

### Tall Grass and Item Discovery
1. No piece starts a game holding any item (`held_item = Item.NONE` for all pieces at game start).
2. Exactly 4 items (always Thunderstone + 3 drawn randomly from {WaterStone, FireStone, LeafStone, BentSpoon}) are placed in random distinct squares in the middle zone (0-indexed rows 2–5) at game start.
3. A non-Pokeball piece moving onto an unexplored grass square reveals it to both players; if an item is present the piece auto-picks it up (subject to overflow rules).
4. A piece already holding an item that would acquire a second triggers **overflow**: the move encodes which item to keep and where to drop the other (nearest open square of the player's choice). Legal move generation produces one Move per valid (keep, drop-location) combination.
5. Pokeballs (Stealballs, Masterballs, Healballs, Master Healballs) moving through unexplored grass squares do not reveal them and do not interact with items.
6. **Expelled Pokemon** (Healball release or automatic discharge) landing on an unexplored grass square immediately explore it per standard rules.
7. Pokeball capture of an item-holding piece drops the item on the capture square as a floor item visible to both players.
8. Standard KO of an item-holding piece: attacker auto-picks up if holding nothing; otherwise overflow applies (encoded in the attack Move).
9. Foresight KO of an item-holding piece drops the item on the vacated square as a floor item visible to both players (no player choice required).
10. Trading is legal when one or both pieces hold `Item.NONE` (a player may pass an item to a teammate).
11. The bot receives a masked `GameState` with `hidden_items = []`; it has no knowledge of unexplored grass contents.
12. `state_to_dict` / `state_from_dict` round-trip all new state fields cleanly.
13. A `player_view_of_state(state, team)` function exists that correctly masks hidden item identities for each player's perspective.

### Pokeball Catch Rates
14. A standard Stealball targeting any piece other than Mew uses HP-based catch rates: 25% at full health, 50% at 50% ≤ HP < 100%, 75% below 50% HP.
15. A standard Stealball targeting Mew uses: 20% at full health, 40% at 50% ≤ HP < 100%, 60% below 50% HP.
16. Master Stealball (Masterball) retains guaranteed capture (no change to existing 100% logic).

### HP Normalization and Eeveelution Changes
17. Per-piece HP values match the spec table: Eevee 150, Vaporeon 440, Jolteon 200 (all other values are already correct).
18. Vaporeon, Flareon, Leafeon, and Jolteon gain Quick Attack using base-Eevee movement (king adjacency only, NORMAL type, 50 base damage). **Espeon does not get QA** — its attacks are Foresight and Psywave only. Standard queen-range ATTACK moves are removed from Espeon's move generator. Jolteon gains 2-square diagonal jump moves (all four diagonal directions, unobstructed) on top of Raichu's full pattern. Raichu and Jolteon's 2-square cardinal moves are unobstructed — they jump over any intermediate pieces.
19. Espeon's **Psywave** (`ActionType.PSYWAVE`) fires from Espeon's position along all 8 queen-movement rays simultaneously, stopping at the first obstacle per ray. Non-Psychic Pokemon take `80 − 10×n` damage (n = empty squares between Espeon and target; min damage 20 on this board), friend and foe equally. Psychic-type Pokemon (Mew, Espeon), Stealballs, and Healballs all stop the ray with no damage and no destruction. Foresight likewise has no effect on Stealballs — if a Stealball occupies the target square when Foresight resolves, the effect fizzles.
20. Flareon's **Flare Blitz** (`ActionType.ATTACK`) deals 180 base FIRE damage and causes Flareon to take 40 recoil damage after the attack resolves. Recoil can KO Flareon. QA (`ActionType.QUICK_ATTACK`) has no recoil.
21. Leafeon's incoming damage is reduced by 40 applied to the attacker's **base damage before type effectiveness** is calculated. The reduced base has a floor of 1 before the multiplier is applied.
22. When the opposing player uses Foresight, the player's client shows only that **Mew or Espeon used Foresight** — the target square is not broadcast. The caster's player sees the target normally.

### Healball Rule Changes
21. Only injured Pokemon (current HP < max HP) may enter a Healball. Full-HP Pokemon are blocked from entry regardless of direction.
22. An injured Pokemon may move forward (one step in its team's advancing direction) directly into a Healball on that square — the Healball stores and heals it identically to standard collection.
23. Master Healball immediately restores the stored Pokemon to full HP at the moment of entry. The Pokemon remains stored until released or auto-discharged; it does not auto-release due to full HP on entry.

### Healball Rule Changes
23. Only injured Pokemon (current HP < max HP) may enter a Healball. Full-HP Pokemon are blocked from entry regardless of direction.
24. An injured Pokemon may move forward (one step in its team's advancing direction) directly into a Healball on that square — the Healball stores and heals it identically to standard collection.
25. Master Healball immediately restores the stored Pokemon to full HP at the moment of entry. The Pokemon remains stored until released or auto-discharged; it does not auto-release due to full HP on entry.

### Testing
26. All existing tests pass. New tests cover each criterion above, including edge cases: overflow with equidistant drop squares, expelled-Pokemon exploration, Foresight KO drop, Pokeball capture drop, exploring an already-explored square, Mew vs. non-Mew catch rate bins, Leafeon reduction applied to base (not final) damage, Psywave damage at various separations, Psywave Stealball destruction, Psywave Psychic-type immunity, QA for four eeveelutions (not Espeon), forward Healball entry, Master Healball instant heal with no auto-release, and Foresight target masking in player view.

---

## WP Groundwork (Included in This Sprint)

Low-cost structural changes that prevent painful refactoring when the Wild Pokemon update lands. None of these require building any WP logic.

| Change | File | Notes |
|---|---|---|
| `Team.WILD = auto()` | `engine/state.py` | Unused placeholder; all team-checking code silently handles it |
| `TALL_GRASS_ROWS = range(2, 6)` | `engine/state.py` | Single definition of the middle zone; never inline the indices |
| `attempt_capture(pokeball, target)` stub | `engine/rules.py` | Raises `NotImplementedError("Wild Pokemon update")` |

---

## Files and Systems Affected

### `engine/state.py`

- **`Team` enum**: Add `WILD = auto()`.
- **`TALL_GRASS_ROWS`**: New module-level constant `range(2, 6)` (0-indexed rows 2–5, equivalent to rows 3–6 in the 1-indexed notation used in the rules documents).
- **`Piece.create()`**: Change `held_item=stats.default_item` → `held_item=Item.NONE`. All pieces start empty-handed.
- **`PIECE_STATS` / `PieceStats.default_item`**: Retain the field. It documents the intended evolution item for each piece type and will be referenced during WP item assignment. It is no longer used in `Piece.create()`.
- **`PIECE_STATS` HP values**: Update the following entries (all others are already correct):
  - `EEVEE`: `max_hp` 120 → 150
  - `VAPOREON`: `max_hp` 220 → 440
  - `JOLTEON`: `max_hp` 220 → 200
- **New `HiddenItem` dataclass**: `(item_type: Item, row: int, col: int)`. An item entity whose location is an undiscovered tall grass square. Full engine truth; not sent to players or bot.
- **New `FloorItem` dataclass**: `(item_type: Item, row: int, col: int)`. A dropped item on an explored square. Visible to both players.
- **`GameState`**: Add three new fields:
  - `hidden_items: list[HiddenItem]` — items not yet found by any player.
  - `floor_items: list[FloorItem]` — items resting on explored squares.
  - `tall_grass_explored: frozenset[tuple[int, int]]` — middle-zone squares that have been revealed.
- **`GameState.new_game()`**: Select 4 items from pool (Thunderstone always included; 3 random from remaining 4). Place each on a random distinct square within `TALL_GRASS_ROWS`. Populate `hidden_items`; initialize `tall_grass_explored` as empty.
- **`GameState.copy()`**: Copy all three new fields (shallow list copy sufficient; dataclasses are replaced not mutated during move application).
- **`GameState.from_dict()`**: Deserialize new fields.

### `engine/moves.py`

**Overflow encoding:**
- **`Move` dataclass**: Add three optional overflow fields, `None` when no overflow occurs:
  - `overflow_keep: Optional[str]` — `"existing"` or `"new"`.
  - `overflow_drop_row: Optional[int]`
  - `overflow_drop_col: Optional[int]`
- **`Move.to_dict()`**: Include the three new fields.
- **Per-piece move generators**: For MOVE actions to unexplored grass squares where the moving piece already holds an item, enumerate all valid overflow resolutions: 2 keep-choices × N valid drop-squares (nearest open squares: explored, unoccupied by piece/Pokeball/floor-item). Each combination is a separate `Move`. Non-overflow moves leave these fields `None`.
- For ATTACK moves: same overflow enumeration when the attacker holds an item and the target also holds one.
- **`_trade_moves`**: No change. The existing `neighbor.held_item != piece.held_item` filter already permits `NONE ↔ item` trades.
- Import `TALL_GRASS_ROWS` from `state`.

**Eeveelution Quick Attack:**
- Add a `_eeveelution_quick_attacks(piece, state)` helper (or reuse `_eevee_quick_attacks` directly) and call it from `_vaporeon_moves`, `_flareon_moves`, `_leafeon_moves`, and `_jolteon_moves`. QA uses king adjacency movement regardless of the eeveelution's enhanced movement pattern. Damage type and base remain as Eevee's QA: NORMAL type, 50 base damage.
- **Espeon does not get QA.** Also remove the existing `ATTACK` move generation from `_espeon_moves` — Espeon's only offensive actions are `FORESIGHT` and `PSYWAVE`.

**Psywave:**
- Add `PSYWAVE = auto()` to the `ActionType` enum.
- In `_espeon_moves`, add one `Move(piece.row, piece.col, ActionType.PSYWAVE, piece.row, piece.col)` — the move targets Espeon's own square as a sentinel (the effect is board-wide, not targeted).
- Psywave is always available (no per-turn restriction like Foresight's consecutive-use block).

**Jolteon movement and Raichu unobstructed cardinals:**
- Add `_JOLTEON_DIAG_JUMPS = [(2,2),(2,-2),(-2,2),(-2,-2)]` and include these in `_jolteon_moves` as unobstructed jump moves (no intermediate-square check).
- In `_raichu_extra_cardinals`, remove the `if state.board[mid_r][mid_c] is not None: continue` obstruction check. Raichu's 2-square cardinal moves leap over intermediate pieces. Apply the same change for `_jolteon_moves` where it calls or reuses this logic.

**Healball forward entry:**
- Add a `_forward_healball_entry(piece, state)` helper: checks the square 1 step in the piece's forward direction (`+1` row for RED, `-1` row for BLUE). If that square holds a friendly empty Healball and the piece is injured (`current_hp < max_hp`) and not Pikachu and storing would leave ≥ 1 other piece on the board, return one MOVE to that square. Call this helper from every non-pawn, non-Healball pokemon move generator.

### `engine/rules.py`

**Tall grass and item discovery:**
- **`_do_move()`**: After resolving Healball storage (see below), if the destination is in `TALL_GRASS_ROWS` and not yet in `tall_grass_explored`, call `_explore_tall_grass(state, piece, move)`. Also handle the new "pokemon moves into Healball" case: if `old_target` is a friendly Healball and the moving piece is not a Healball type, store the piece inside the Healball (set `old_target.stored_piece = piece`, call `_safetyball_heal`, remove piece from its original square) rather than overwriting the Healball.
- **`_do_release()` and `_discharge_unmoved_safetyballs()`**: After placing the stored Pokemon on the board, if its landing square is in `TALL_GRASS_ROWS` and unexplored, call `_explore_tall_grass(state, released_piece, move=None)`. (No overflow fields available; server applies default resolution.)
- **`_explore_tall_grass(state, piece, move)` (new)**: Add the square to `tall_grass_explored`. Search `hidden_items` for an item at that square. If found, remove it from `hidden_items` and call `_handle_item_encounter`.
- **`_handle_item_encounter(state, piece, item, move)` (new)**: If `piece.held_item == Item.NONE`, auto-pickup. Otherwise apply overflow from `move.overflow_keep` and `move.overflow_drop_*`. If `move` is `None` or overflow fields are absent (bot / discharge path), keep existing item, drop new item at the first nearest open square in row-major scan order.
- **`_capture()`**: After the attacker occupies the target's square, if `target.held_item != Item.NONE`: auto-pickup if attacker is empty-handed, else call `_handle_item_encounter`.
- **`_capture_both()`**: If `target.held_item != Item.NONE`, add a `FloorItem` at `(target_row, target_col)`.
- **`_resolve_foresight()`**: After a KO, if the killed piece held an item, add a `FloorItem` at the vacated square.
- **`_do_quick_attack()`**: Apply the same item-handling as `_capture()` when the attack results in a KO.
- **`attempt_capture(pokeball, target)` stub (new)**: Standalone function raising `NotImplementedError("Capture logic reserved for Wild Pokemon update")`.

**Psywave — `_do_psywave(state, piece, move)` (new)**: For each of the 8 queen-movement directions, walk outward from `piece`'s square counting empty squares (`n`). On the first occupied square in that ray:
  - Non-Psychic Pokemon (`pokemon_type != PokemonType.PSYCHIC`, any team): deal `max(10, 80 - 10 * n)` damage; if HP ≤ 0, remove and trigger item drop. Stop.
  - Psychic-type Pokemon, Stealball (`POKEBALL` / `MASTERBALL`), or Healball (`SAFETYBALL` / `MASTER_SAFETYBALL`): stop with no effect — no damage, no destruction.
  Add `PSYWAVE` to the `_apply_deterministic` dispatch table.

**Foresight — Stealball immunity**: In `_resolve_foresight`, change the guard from `target.piece_type not in SAFETYBALL_TYPES` to `target.piece_type not in PAWN_TYPES`. This makes Foresight fizzle silently on both Stealballs and Healballs.

**Variable Pokeball catch rates:**
- Remove `_POKEBALL_CAPTURE_PROB = 0.5`.
- Add `_pokeball_catch_prob(target: Piece) -> float`: branches on `target.piece_type == PieceType.MEW`, then bins by HP percentage:
  - Non-Mew: `1.0 → 0.25`, `0.5 ≤ x < 1.0 → 0.50`, `< 0.5 → 0.75`
  - Mew: `1.0 → 0.20`, `0.5 ≤ x < 1.0 → 0.40`, `< 0.5 → 0.60`
  - HP percentage = `target.current_hp / target.max_hp`
- In `apply_move`, replace `_POKEBALL_CAPTURE_PROB` with `_pokeball_catch_prob(target)`.
- Master Stealball (MASTERBALL): no change — it bypasses the probability path entirely via `_capture_both` in `_do_attack`.

**Flareon — Flare Blitz:**
- Update `_BASE_DAMAGE[PieceType.FLAREON]` from 100 to 180.
- In `_do_attack`, after resolving damage to the target, if `piece.piece_type == PieceType.FLAREON`, apply 40 recoil damage to `piece` (`piece.current_hp -= 40`). Recoil is applied regardless of whether the target was KO'd. If recoil reduces Flareon to ≤ 0 HP, remove it from the board (treated as a KO).
- Flareon's `pokemon_type` is already `PokemonType.FIRE` in `PIECE_STATS`; type effectiveness applies without further changes.
- QA (`ActionType.QUICK_ATTACK`) is a distinct action type and does not trigger recoil.

**Leafeon damage reduction:**
- In `calc_damage_with_multiplier`, if `target.piece_type == PieceType.LEAFEON`, subtract 40 from the attacker's `base` damage before the type effectiveness multiplier is applied: `effective_base = max(1, base - 40)`. The multiplier is then applied to `effective_base`. This means the reduction is more impactful against neutral/resisted hits and less impactful against super-effective ones.

**Master Healball instant heal:**
- In `_safetyball_heal`: for `MASTER_SAFETYBALL`, set `stored.current_hp = stored.max_hp` and **do not** trigger the auto-release check. For `SAFETYBALL` (basic), behavior is unchanged (heal ¼ max HP per turn, auto-release when full).

### `engine/zobrist.py`

- Review whether `tall_grass_explored` and `floor_items` need to be hashed for transposition table correctness. Both fields affect legal moves and item outcomes, so they should be incorporated. Add Zobrist keys for each `(row, col)` in `TALL_GRASS_ROWS` (explored/unexplored bit) and each `(row, col, item_type)` combination for floor items.

### `app/game_logic/serialization.py`

- **`state_to_dict()`**: Add `hidden_items`, `floor_items`, and `tall_grass_explored` to the output.
- **`state_from_dict()`**: Deserialize all three new fields.
- **New `player_view_of_state(state, team, id_map)`**: Returns a serialized dict with:
  - `hidden_items` omitted entirely.
  - Items held by opponent pieces: identity masked (`held_item` → `"UNKNOWN"`).
  - `floor_items` included in full (visible to both players).
  - `tall_grass_explored` included in full.
  - Opponent's `pending_foresight`: target coordinates (`target_row`, `target_col`) stripped. Preserve only a notification payload indicating which piece type (Mew or Espeon) cast it, derivable from `caster_row` / `caster_col` in the full state.

### `bot/server.py`

- When constructing the `GameState` for MCTS, use `player_view_of_state` (or manually strip `hidden_items`) so the bot operates on a masked state. See Design Decisions.

### `frontend/` — Second Priority (Required for Sprint Completion)

Frontend work begins after the backend/engine layer is stable and tests pass. All frontend changes consume the existing API shape produced by `player_view_of_state`.

**Board rendering:**
- Darken all 32 unexplored middle-zone squares at game start (rows 3–6 in 1-indexed display). All middle squares begin darkened regardless of whether they contain an item.
- When a square transitions from unexplored to explored (signaled by the square appearing in `tall_grass_explored` in the state update), un-darken it with a reveal animation.

**Item visibility:**
- For the active player's own pieces: display the held item identity on the piece.
- For opponent pieces: display a generic "holding item" indicator when `held_item == "UNKNOWN"`; show no indicator when the opponent holds nothing.
- Display all `floor_items` on their squares, identities visible to both players.

**Exploration event notifications:**
- When the active player's Pokemon explores a grass square and finds an item, show a notification with the item's name and icon.
- When the opponent explores a grass square and finds an item, show a neutral "item found" notification (no identity).
- When either player explores a square with no item, no notification is needed (the square simply un-darkens).

**Overflow UI:**
- When a player's move would trigger item overflow (piece already holds item, acquires second), present a selection prompt: display both items, ask which to keep. After the player selects which to keep, if there are multiple equidistant valid drop squares, present a secondary prompt to choose the drop location.
- The overflow choice completes the move encoding before the move is submitted to the API.

### `tests/` (new and updated)

- **`tests/test_tall_grass.py`** (new): Items §1–13 and §24.
- **`tests/test_catch_rates.py`** (new): Criteria §14–16 — all HP bins for Mew and non-Mew, Masterball passthrough.
- **`tests/test_eeveelutions.py`** (new or extend existing): Criteria §17–20 — HP values, QA generation and damage for each eeveelution, Flareon 150 damage, Leafeon reduction including floor.
- **`tests/test_healball.py`** (new or extend existing): Criteria §21–23 — full-HP rejection, forward entry move generation and application, Master Healball instant heal and no auto-release on entry.

---

## Documented Design Decisions

### Pokeball Capture of Item-Holding Piece

When a Pokeball captures a Pokemon holding an item, the item is dropped on the **capture square** (the square the captured Pokemon occupied).

**Alternatives considered:**
- *Drop on the Pokeball's origin square*: less intuitive; the item would appear behind the action.
- *Item is lost*: punishes positional play near tall grass; removes item permanently without counter-play.

**Chosen rationale:** Consistent with standard KO behavior (items always survive a capture) and creates natural strategic tension around Pokeball use near contested grass areas.

**Status:** Open for revision after playtesting.

---

### Bot Hidden Item Visibility ("Blind Bot")

The bot receives a masked `GameState` with `hidden_items = []`. It has no knowledge of which unexplored grass squares contain items and cannot strategize around item positions.

**Alternatives considered:**

- **Oracle bot**: Bot receives full `hidden_items`. Creates a persistent information advantage the human player can never have; rejected.
- **Belief-state MCTS**: Bot maintains probability distributions over item locations and samples from them during rollouts. Most principled; significantly increases MCTS complexity and requires careful integration with the transposition table. Reserved for a future improvement sprint.
- **Blind bot (chosen)**: Bot treats all unexplored grass squares as empty. Items are discovered incidentally, not sought. Accepted tradeoff: when a bot move inadvertently triggers overflow (piece has item, grass square also has item), the bot carried no overflow fields. The server applies a deterministic default: keep existing item, drop new item at the first nearest open square in row-major scan order.

**Status:** Revisit after Wild Pokemon update. Belief-state approach becomes more valuable when WPs actively move items around the board.
