# PokeChess ML Bot — Task Log

Post-task review summaries for each completed implementation task.

---

## Task #1 — Project Scaffold

**Deliverables:** CLAUDE.md, requirements.txt, .gitignore, stub modules for `engine/` and `bot/`

---

### Workflow Walkthrough

**Step 1 — Package layout**

Created the `engine/` and `bot/` Python packages with `__init__.py` files. All game logic lives in `engine/` (no ML dependencies); the MCTS bot lives in `bot/` (depends on `engine`, no frontend coupling). `cpp/` is reserved for the Phase 3 C++ port.

**Step 2 — Stub files**

Each module was stubbed with its full public interface (docstrings, type signatures, `raise NotImplementedError` bodies) so the overall architecture is visible before any logic is written:

| File | Role |
|---|---|
| `engine/state.py` | `GameState`, `Piece`, enums, MATCHUP table |
| `engine/moves.py` | `Move` dataclass, `ActionType` enum, `get_legal_moves()` |
| `engine/rules.py` | `apply_move()`, `is_terminal()`, `hp_winner()` |
| `engine/zobrist.py` | Zobrist hashing for transposition table |
| `bot/mcts.py` | `MCTSNode`, `MCTS` class |
| `bot/ucb.py` | `ucb1()` formula |
| `bot/transposition.py` | `TranspositionTable` class |

**Step 3 — Post-scaffold review and patches**

A `/simplify` review caught several design issues that were patched before any logic was written:

- Three parallel `PieceType` dicts (`PIECE_TYPE`, `MAX_HP`, `DEFAULT_HELD_ITEM`) consolidated into `PIECE_STATS: dict[PieceType, PieceStats]` — single source of truth, cache-friendly
- Inline `is_king`/`is_pawn` tuples replaced with `KING_TYPES` and `PAWN_TYPES` frozensets for O(1) membership and a single authoritative definition
- `Piece.copy()` manual field repetition replaced with `dataclasses.replace(self)`
- `all_pieces()` two-pass (collect all, then filter) collapsed to a single comprehension
- `MCTS.exploration_c=None` implicit default replaced with explicit `DEFAULT_C` import
- `pending_foresight` changed from `Optional[ForesightEffect]` (single slot) to `dict[Team, Optional[ForesightEffect]]` — both teams can have Foresight queued simultaneously
- `ForesightEffect` shallow copy in `GameState.copy()` fixed with `dataclasses.replace(fx)`
- `MATCHUP` table extended with `PokemonType.NONE` row and column
- Task reference comments (`"Implemented in Task #X"`) stripped from all stubs

---

## Task #2 — GameState and Piece Data Structures

**90 tests, 90 passed, 0.09s**

---

### Workflow Walkthrough

**Step 1 — Coverage mapping**

Before writing a single test, every exported symbol from `engine/state.py` was catalogued: `PIECE_STATS`, `KING_TYPES`, `PAWN_TYPES`, `MATCHUP`, `Piece`, `GameState`, and `new_game()`. Each got its own test class so failures localize immediately.

**Step 2 — Data contract tests (`TestPieceStats`, `TestMatchup`)**

These guard against silent data-entry mistakes in the lookup tables — wrong HP, swapped type, missing key. Key choices:
- Parametrized per-PieceType so a new entry added to `PIECE_STATS` without a test immediately surfaces as a gap
- MATCHUP tested for completeness (every type × every type) *and* for value validity (only `{0.5, 1.0, 2.0}` allowed), so a typo like `1.5` fails loudly

**Step 3 — Classification tests (`TestPieceClassification`)**

`KING_TYPES` and `PAWN_TYPES` are disjoint frozensets. Tests assert membership for every relevant PieceType in both directions (is-true and is-false), preventing the common mistake where a newly added evolution isn't placed in the right set.

**Step 4 — Piece lifecycle tests (`TestPieceCreate`, `TestPieceCopy`)**

Verified that `Piece.__init__` wires fields correctly from `PIECE_STATS` (full HP, default item, correct `pokemon_type`), with special cases for Eevee (no item) and Pokeball (zero HP, NONE type). `TestPieceCopy` checks that mutations to HP and item in the copy don't bleed back — this would have caught the pre-fix shallow-copy bug.

**Step 5 — Board layout tests (`TestNewGame`)**

`new_game()` is the entry point for every game. Tests assert:
- Active player = RED, turn = 1, foresight dicts clear
- Exact piece counts (32 total, 16/team, 8 pokeballs/team)
- Middle rows 2–5 empty
- Back rank composition parametrized for both Red (row 0) and Blue (row 7)
- Pawn ranks (row 1 Red, row 6 Blue) all Pokeballs
- Every piece at full HP with its default item

**Step 6 — GameState contract tests (`TestPieceAt`, `TestAllPieces`, `TestGameStateCopy`)**

`TestGameStateCopy` is the most important: it exercises the six independence invariants that `GameState.copy()` must satisfy — HP, item, board membership, foresight flags, pending foresight dict, and the ForesightEffect deep copy. The last one (`test_foresight_effect_deep_copied`) would have caught the pre-fix bug where `dataclasses.replace()` was missing and both original and copy shared the same ForesightEffect object.

---

### What the tests protect going forward

| Risk | Test |
|---|---|
| New PieceType added without PIECE_STATS entry | `test_every_piece_type_has_entry` |
| New evolution not added to KING_TYPES | `test_is_king_false` parametrize |
| MATCHUP typo (wrong multiplier) | `test_all_multipliers_are_valid` |
| `new_game()` board layout regression | Full `TestNewGame` suite |
| `copy()` made shallow again | `TestGameStateCopy` all 6 tests |
| ForesightEffect sharing bug reintroduced | `test_foresight_effect_deep_copied` |

---

## Task #3 — Move Generation: Standard Pieces

**44 tests, 44 passed, 0.06s**
Pieces covered: Squirtle (Rook), Charmander (Knight), Bulbasaur (Bishop), Mew (Queen)

---

### Workflow Walkthrough

**Step 1 — Geometry helpers**

Two shared primitives handle all sliding piece movement:

- `_sliding_squares(piece, state, directions)` walks each ray until it hits a board edge, a friendly (ray breaks, square excluded), or an enemy (ray breaks, square added to attackable). Returned as `(empties, enemies)` — the same output feeds MOVE generation, ATTACK generation, and Foresight targeting without any duplication.
- `_trade_moves(piece, state)` scans all 8 adjacencies for friendlies holding a *different* item. Filtering on `held_item != piece.held_item` prevents no-op trades without needing a separate game rule.

**Step 2 — Per-piece generators**

| Piece | Pattern | Special |
|---|---|---|
| Squirtle | Slides on `_ROOK_DIRS` | — |
| Charmander | 8 fixed L-jumps, no ray casting | Passes over all intervening pieces |
| Bulbasaur | Slides on `_BISHOP_DIRS` | — |
| Mew | Slides on `_QUEEN_DIRS` | 4 attack slots per target; Foresight |

**Step 3 — Mew's move slot design**

Mew generates 4 separate `ATTACK` moves per reachable enemy — one per slot (0–3). The distinction matters in `rules.py` (Task #6) where each slot will deal different damage. For MCTS, having 4 choices per target is intentional: the bot will learn which slot is optimal against each target type. Foresight uses `move_slot=None` since its damage is computed separately.

**Step 4 — Dispatch table**

`_PIECE_MOVE_FN` maps `PieceType → generator`. Unknown types return `None` (`.get()`), so Tasks #4 and #5 can extend the table incrementally without touching `get_legal_moves`. Unimplemented pieces are silently skipped rather than raising.

**Step 5 — Test bug caught during the run**

Two initial failures revealed a test design issue: `get_legal_moves` returns moves for **all** active pieces, so tests that put multiple RED pieces on the board must filter by origin square. Added `moves_from(moves, row, col)` helper and fixed the two affected tests. Both failures were in the tests, not the implementation.

---

### What the tests protect going forward

| Risk | Test |
|---|---|
| Off-board target generated | `test_no_moves_off_board` (all 4 pieces) |
| Sliding piece passes through friendly | `test_friendly_blocks_ray_*` |
| Sliding piece passes through enemy | `test_enemy_blocks_*_behind_it` |
| Knight erroneously blocked by adjacent piece | `test_jumps_over_friendly/enemy` |
| Mew generates wrong number of attack slots | `test_attack_generates_four_slots_per_target` |
| Foresight allowed on consecutive turns | `test_foresight_blocked_after_used_last_turn` |
| Foresight flag from one team bleeds into other | `test_foresight_available_for_blue_when_only_red_blocked` |
| TRADE between pieces with same item | `test_no_trade_with_same_item` |
| TRADE with enemy | `test_no_trade_with_enemy` |

---

## Task #4 — Move Generation: Pokeball and Masterball

**67 move tests (23 new), 159 total — all passing**

---

### Pokeball and Masterball movement rules

**Pokeball:**
- Up to 2 squares forward (own direction) — blocked by pieces
- Up to 2 squares horizontal (left or right) — blocked by pieces
- 1 square forward-diagonal (left and right)

**Masterball adds:**
- Up to 2 squares backward — blocked by pieces
- 1 square backward-diagonal (left and right)

RED forward = +row (toward row 7); BLUE forward = -row (toward row 0).

---

### Workflow Walkthrough

**Step 1 — Direction abstraction**

The key insight for pawns in a two-sided game is encapsulating "forward" per team. `_forward(team)` returns `+1` for RED (moving toward row 7) and `-1` for BLUE (moving toward row 0). Every directional move is expressed relative to this, so the same generator works correctly for both sides with no team-specific branching.

**Step 2 — `_add_steps` helper**

`_sliding_squares` from Task #3 is unbounded and returns lists. Pokeballs and Masterballs need bounded movement (max 2 squares) that directly appends to an existing move list. `_add_steps(piece, state, moves, dr, dc, max_steps)` fills that role — same blocking semantics (friendly breaks the ray, enemy gets attacked and breaks), but stops after at most `max_steps` squares. It's used for all 5–8 directions per piece type.

**Step 3 — Pokeball vs Masterball**

Both generators are written explicitly (rather than Masterball calling Pokeball internally) to keep each function flat and readable. The relationship is clear from the comments.

**Step 4 — Three test failures caught → same root cause as Task #3**

When a blocking piece is placed on the board, `get_legal_moves` returns moves for *all* active pieces. The blocking Squirtle generates its own MOVE to the "blocked" square, making the assertion appear to fail. Fix: use `moves_from(moves, row, col)` to scope each assertion to only the piece being tested. Pattern is now established and won't surprise us again.

---

### What the tests protect going forward

| Risk | Test |
|---|---|
| Pokeball moves backward | `test_no_backward_diagonal_for_pokeball`, `test_forward_direction_*` |
| RED/BLUE forward directions swapped | `test_forward_direction_red`, `test_forward_direction_blue` |
| 2-square move ignores blocking at square 1 | `test_*_blocked_at_1_prevents_reaching_2` |
| Off-board target generated at edge/corner | `test_no_moves_off_board`, `test_edge_column_limits_horizontal` |
| Masterball missing backward moves | `test_has_backward_straight`, `test_has_backward_diagonals` |
| BLUE Masterball backward direction wrong | `test_blue_masterball_backward_toward_high_rows` |

---

## Task #5 — Move Generation: Kings and All Evolutions

**132 move tests (65 new), 224 total — all passing**
Pieces covered: Pikachu, Raichu, Eevee, Vaporeon, Flareon, Leafeon, Jolteon, Espeon

---

### Workflow Walkthrough

**Step 1 — Shared king foundation**

`_king_standard_moves` handles the 1-square, 8-direction movement common to all 8 king types. All generators call it and layer their special abilities on top.

**Step 2 — Pikachu / Raichu**

Pikachu appends one `EVOLVE` move targeting its own square (evolution is in-place, no movement, costs the turn). `move_slot=None` since there's only one target evolution. Raichu is the simplest generator: king moves + trade only.

**Step 3 — Eevee evolution gating**

`_EEVEE_EVOLUTION_SLOT` maps held item → `move_slot` (0–4). If Eevee holds no stone, no EVOLVE move is generated — the player must first trade to acquire one. The move_slot value tells `rules.py` which `PieceType` to create without having to re-derive it from the item.

| move_slot | Evolution | Required item |
|---|---|---|
| 0 | Vaporeon | WATERSTONE |
| 1 | Flareon | FIRESTONE |
| 2 | Leafeon | LEAFSTONE |
| 3 | Jolteon | THUNDERSTONE |
| 4 | Espeon | BENTSPOON |

**Step 4 — Quick Attack**

`_eevee_quick_attacks` iterates over all 8 adjacent empty squares as potential destinations, then for each checks all 8 adjacent squares from the destination for enemies. This produces `(dest, attack_target)` pairs encoded as `QUICK_ATTACK` with `secondary_row/col`. The two key invariants — destination must be empty, secondary must be an enemy — are enforced during generation, not deferred to `rules.py`.

**Step 5 — Espeon Foresight**

Reuses the consecutive-turn guard (`foresight_used_last_turn`) from Mew but limits target squares to adjacent only (king movement range), consistent with the "attack range = movement range" rule.

**Step 6 — Two test bugs caught**

- `test_does_not_attack_friendly`: `targets()` collected ALL action types including TRADE, which legitimately targets friendly pieces (item swap). Fixed to check only ATTACK and MOVE targets.
- `test_unimplemented_piece_types_skipped_gracefully`: Pikachu was now implemented, so the test needed replacement. Replaced with `test_all_piece_types_handled` which verifies every piece type generates at least one move without raising.

---

### What the tests protect going forward

| Risk | Test |
|---|---|
| Any king moves off-board | `test_no_moves_off_board` (parametrized, all 8 types) |
| Pikachu missing EVOLVE or Raichu having one | `test_always_has_evolve`, `test_raichu_has_no_evolve` |
| Eevee evolution available without a stone | `test_no_evolve_without_item` |
| Wrong move_slot for a given item | `test_evolve_slot_matches_item` (5 parametrized cases) |
| Quick Attack destination is not empty | `test_quick_attack_target_is_empty_destination` |
| Quick Attack secondary is not an enemy | `test_quick_attack_secondary_is_enemy` |
| Espeon Foresight exceeds king range | `test_foresight_targets_only_adjacent` |
| Espeon Foresight targets friendly | `test_foresight_excludes_friendly_squares` |
| Espeon has EVOLVE or vice versa | `test_espeon_has_no_evolve` |
