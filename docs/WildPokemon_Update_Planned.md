# PokeChess — Wild Pokemon Update (Planned / Pre-Ratification)

This document captures the current design planning for the Wild Pokemon feature, intended for a future development sprint after the Tall Grass Update is stable and playtested. The design reflects decisions made as of the planning session but contains open questions that must be resolved before ratification.

---

## 1. Overview

Wild Pokemon (WP) introduce a neutral third faction — "Green Team" — that lives in the tall grass and behaves autonomously. They are hostile to both players, hold the game's evolution items, and can be captured using Pokeballs. This update builds directly on the Tall Grass Update infrastructure.

---

## 2. Wild Pokemon Composition

- There are exactly **4 Wild Pokemon** on the board, one of each non-king pokepiece type (Rook, Knight, Bishop, Queen — and their corresponding Pokemon with associated types).
- WPs are distinct from player pieces and belong to neither Red nor Blue team.
- Each WP holds one evolution item:
  - **Mew** always holds the **Thunderstone**.
  - The remaining 3 WPs each hold one item drawn randomly from the remaining pool: Fire Stone, Water Stone, Leaf Stone, Bent Spoon.
- This means **all 4 items are held by WPs** — there are no standalone items hidden in the tall grass in this update.

---

## 3. WP Movement — "Mother Nature" Turn

- **One WP moves at the start of every player turn** (i.e. once per Red turn and once per Blue turn).
- Which WP moves each turn is selected randomly.
- WPs may only move to **adjacent tall grass squares**.
- If a WP is isolated (no adjacent tall grass squares available) it cannot move that turn.
- **Attack override:** If a player's Pokemon occupies a square adjacent to a WP, the WP attacks that Pokemon instead of wandering.
- If multiple player Pokemon are adjacent to one or more WPs, the attack target is selected randomly.

---

## 4. Player Encounters with WPs

When a player's Pokemon moves through the tall grass and reaches a square occupied by a WP, movement stops and the player must choose one of two options:

- **Attack:** The player's Pokemon attacks the WP. Resolution TBD (see Open Questions).
- **Run Away:** The player's Pokemon retreats one square, to a square outside the WP's range. This ends the player's turn.

---

## 5. Capture Mechanics

- WPs can be captured using a **Pokeball within range** of the WP (range definition TBD — see Open Questions).
- Both Stealballs and Healballs can be used for capture attempts.
- Capture success is probabilistic and tied to the WP's remaining health.

### Standard WP Catch Rates (all pokepieces except Mew)
| HP State | Catch Rate |
|---|---|
| Full health | 25% |
| Between half and full health | 50% |
| Below half health | 75% |

### Mew Catch Rates
| HP State | Catch Rate |
|---|---|
| Full health | 10% |
| Above 75% health | 25% |
| Above 50% health | 40% |
| Above 25% health | 60% |
| 25% health or below | 75% |

### Capture Outcome
- On a **successful capture**, the WP is removed from the board and its held item appears on the **starting square corresponding to that pokepiece type** (e.g. a captured Rook WP places its item on a1 or h1).
- If the starting square is **occupied**, the item is lost.
- The capturing player does **not** receive the WP as a recruited piece.
- The Pokeball used is consumed regardless of success or failure.

---

## 6. Open Design Questions

The following questions were raised during planning and must be resolved before this update can be ratified:

1. **Item distribution:** With all 4 items held by WPs, are there any standalone items hidden in the tall grass, or do items exclusively come from WPs? (Current lean: WPs hold all items, no standalone items.)

2. **Pokeball capture range:** Does "within range" mean the Pokeball could legally move to the WP's square in one move, or is it a fixed adjacency radius? This needs a precise definition, especially given that Stealballs and Healballs have different movement rules.

3. **Attack resolution — player-initiated:** When a player's Pokemon attacks a WP, is it a guaranteed KO (standard chess capture logic), or is there an uncertain outcome? If uncertain, what governs it?

4. **Attack resolution — WP-initiated:** When a WP attacks a player's Pokemon during Mother Nature's turn, is it always a KO? Should the odds differ from player-initiated encounters to avoid over-penalizing players for being near the grass?

5. **Run away definition:** Does retreating one square always end the turn? Can a player run away from the same WP on consecutive turns indefinitely?

6. **WP movement — which WP moves:** Is the WP selected for movement each turn purely random, or round-robin? Does a WP that just attacked still count as having moved for that turn?

7. **WP and explored squares:** Can WPs move onto explored (non-tall-grass) squares within the middle 4 rows, or are they strictly confined to unexplored tall grass?

8. **Mother Nature turn order:** Once WPs are on the board at game start, does Mother Nature have a turn from turn 1, or only after the first WP is revealed by a player encounter?

---

## 7. Implementation Dependencies

This update requires the following Tall Grass Update infrastructure to already be in place:

- Tall grass square state tracking (unexplored, explored-empty, explored-with-item)
- Middle 4 rows as a defined board zone
- Item held-by-piece state and visibility rules
- Pokeball movement and interaction logic

---

## 8. Groundwork to Lay During the Tall Grass Update

The following are concrete, low-cost actions for Claude Code to take during the Tall Grass Update implementation. None of these require building WP logic now — they are structural decisions that will prevent the WP update from requiring painful refactoring of systems that are being built fresh today.

### 8.1 Model Items as Entities, Not Square Properties

When implementing item placement and discovery, do **not** model items as a property of a square (e.g. `square.item = "Thunderstone"`). Instead, model items as independent entities that have a location which can be one of:

- Held by a specific piece (identified by piece ID, not team)
- Residing on a specific square
- Not yet discovered (hidden in tall grass)

This is the single most important structural decision for WP compatibility. When WPs are introduced, they are pieces that hold items — exactly the same held-item relationship that player Pokemon have. If items are square properties, retrofitting "held by a neutral piece" will require reworking the item system from scratch.

### 8.2 Define the Middle 4 Rows as a Named Constant

Do not hardcode row indices (e.g. `rows 3–6`) inline throughout the movement and exploration logic. Define the tall grass zone once as a named constant or config value (e.g. `TALL_GRASS_ROWS = range(3, 7)`). The WP update, and any future update touching this zone, will reference it in many places. A single definition avoids silent inconsistencies if the zone ever changes.

### 8.3 Make the `team` Attribute an Enum with a WILD Placeholder

Piece objects currently have a `team` attribute that is Red or Blue. During the Tall Grass Update, convert this to a proper enum with three values: `RED`, `BLUE`, and `WILD`. The `WILD` value does not need to be used by any logic during this update — it just needs to exist. This is a one-line change now versus a breaking change when WP pieces are introduced and every system that checks `piece.team` needs to handle a third case it was never designed for.

### 8.4 Add a `attempt_capture(target)` Stub to Pokeball Logic

The Pokeball class is being touched during the Tall Grass Update to define its non-interaction with tall grass and items. While that logic is being written, add a stub method:

```python
def attempt_capture(self, target):
    raise NotImplementedError("Capture logic reserved for Wild Pokemon update")
```

This does nothing functionally but signals to future implementers exactly where capture logic belongs and prevents it from being bolted on somewhere inappropriate later.

### 8.5 Do Not Build Any of the Following During This Update

The following belong exclusively to the WP sprint and should not be stubbed, partially implemented, or speculatively designed during the Tall Grass Update. Too many open design questions remain for these to be built responsibly ahead of ratification:

- WP movement or targeting AI
- Mother Nature turn order insertion
- Capture probability logic
- Attack resolution for WP encounters
- WP piece initialization or board placement
