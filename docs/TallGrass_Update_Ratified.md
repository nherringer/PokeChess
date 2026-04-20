# PokeChess — Tall Grass Update (Ratified)

This document describes ratified changes to the PokeChess item system as part of the "Tall Grass Update." These changes replace the prior item initialization logic and introduce a new item discovery and interaction system. Claude Code should treat all rules here as authoritative and implement accordingly.

---

## 1. Overview

The Tall Grass Update replaces the static, deterministic item distribution system with a hidden exploration mechanic. No Pokemon start the game with items. Instead, a subset of evolution items are randomly placed in hidden squares in the middle of the board, and players must explore to find them.

---

## 2. Item Initialization Changes

### 2.1 No Starting Items
- **Previous behavior:** All Pokemon (except Eevee) began the game holding the EV item corresponding to their type.
- **New behavior:** No Pokemon begin the game holding any items. The board starts with no items on any Pokemon.

### 2.2 Item Pool and Selection
- There are 5 possible evolution items in the game pool:
  - Thunderstone
  - Fire Stone
  - Water Stone
  - Leaf Stone
  - Bent Spoon
- At the start of each game, **4 of these 5 items are randomly selected**.
- **The Thunderstone is always one of the 4 selected items.** The remaining 3 are drawn randomly from the other 4.

### 2.3 Item Placement — Tall Grass
- The 4 selected items are **randomly placed in the middle 4 rows of the board** (rows 3–6 on an 8-row board, or the equivalent middle zone).
- Item positions are hidden from both players at game start.
- Squares in the middle 4 rows are visually represented as **darkened ("tall grass") squares**, indicating they have not been explored and may or may not contain a hidden item.
- All middle-zone squares begin darkened regardless of whether they contain an item.

---

## 3. Exploration and Item Discovery

### 3.1 Exploration by Pokemon
- When a **Pokemon** (not a Pokeball) moves onto a darkened tall grass square, the square is **immediately explored**:
  - The square becomes undarkened and is visible to **both players**.
  - If an item is present, the Pokemon **automatically picks it up**.
  - If the Pokemon is already holding an item, see Section 4 (Item Overflow).
- The discovering player learns the **identity** of the found item.
- The opposing player sees only that **an item was found** — the item's identity is **not revealed** to them.

### 3.2 Pokeballs Do Not Explore Tall Grass
- Pokeballs (Stealballs and Safetyballs) **do not explore tall grass squares**.
- A Pokeball may occupy a tall grass square without triggering exploration. The square remains darkened and any hidden item remains hidden.
- A Pokeball **cannot hold items** and does not interact with items in any way.
- Once a Pokeball vacates a tall grass square, the square remains unexplored until a Pokemon moves onto it.
- **Exception — Expelled Pokemon:** When a Pokeball expels a stored Pokemon onto a tall grass square, the Pokemon immediately explores that square upon expulsion, following the standard discovery rules above.

---

## 4. Item Overflow (Holding Multiple Items)

A Pokemon can hold **at most one item** at any time. If a Pokemon holding an item would acquire a second item for any reason:

- The **player controlling that Pokemon** chooses which item to keep and which to drop.
- The dropped item is placed on the **nearest open square** to the current square.
  - An "open square" is defined as: explored (not tall grass), unoccupied by any Pokemon, Pokeball, or existing item.
  - If multiple equidistant open squares exist, the **player controlling that Pokemon** chooses which one the item drops to.
- The dropped item is **visible to both players**, including its identity.

---

## 5. Item Drops on KO

### 5.1 Standard KO (Non-Foresight)
- When a Pokemon holding an item is KO'd by a standard attack:
  - The attacking Pokemon **moves into the vacated square** (standard chess-capture behavior).
  - If the attacking Pokemon is **not holding an item**, it automatically picks up the dropped item.
  - If the attacking Pokemon **is already holding an item**, the Item Overflow rules in Section 4 apply: the player chooses which item to keep, and the dropped item is placed on the nearest open square of the player's choice.

### 5.2 Foresight KO
- When a Pokemon holding an item is KO'd by Foresight:
  - The attacking Pokemon **does not advance** to the vacated square.
  - The item is **dropped on the square vacated by the KO'd Pokemon**.
  - That square is explored and visible to both players, with the item's identity visible to both players.
  - The item remains there and is **free to be picked up by either player's Pokemon**.
- **Edge case — Foresight targeting a Stealball:** Foresight has no effect on Stealballs. If the target square is occupied by a Stealball when Foresight resolves, the effect fizzles with no damage and no item interaction. The Stealball is unaffected. If the Stealball is in an unexplored tall grass square, the square remains unexplored.

---

## 6. Trading

- Trading an item between Pokemon **costs a full turn** for the trading player.
- When a trade occurs:
  - The **receiving player does not learn the identity** of the traded item.
  - The **opposing player** sees only that a trade occurred, not which item was traded.
- **Eevee evolution via trade:** Eevee does not evolve upon receiving any item. Eevee must **use the correct EV item** corresponding to the desired Eeveelution to evolve. A traded item that is not the correct type has no evolution effect.

---

## 7. Voluntary Item Dropping

- Pokemon **cannot voluntarily drop items**. Dropping only occurs as a result of:
  - Picking up a second item (overflow, Section 4).
  - Being KO'd while holding an item (Section 5).

---

## 8. Summary of Key Visibility Rules

| Event | Discovering Player Sees | Opposing Player Sees |
|---|---|---|
| Pokemon explores tall grass with item | Square undarkened + item identity | Square undarkened + "item found" (no identity) |
| Pokemon explores tall grass, no item | Square undarkened, nothing found | Square undarkened, nothing found |
| Item dropped (overflow or KO) | Item identity + drop location | Item identity + drop location |
| Trade occurs | Item identity (their own Pokemon) | Trade occurred (no identity) |
| Foresight used | Target square + which piece cast it | "[Mew / Espeon] used Foresight" — target square is **not revealed** |

---

## 9. Pokeball Catch Rates

### 9.1 Master Stealball
- The Master Stealball always has a **100% catch rate** regardless of the target's health.

### 9.2 Standard Stealball — All Pokemon Except Mew
Catch rate is determined by the target's current HP as a percentage of its maximum HP:

| HP State | Catch Rate |
|---|---|
| 100% (full health) | 25% |
| 50% ≤ HP < 100% | 50% |
| HP < 50% | 75% |

### 9.3 Standard Stealball — Mew
Mew has reduced catch rates reflecting its legendary status:

| HP State | Catch Rate |
|---|---|
| 100% (full health) | 20% |
| 50% ≤ HP < 100% | 40% |
| HP < 50% | 60% |

---

## 10. HP Normalization

The following HP values replace all prior per-piece HP values. These apply to base pieces and carry forward to their evolved forms unless otherwise specified by an eeveelution rule below:

| HP | Pokemon |
|---|---|
| 150 | Eevee |
| 200 | Squirtle, Charmander, Bulbasaur, Pikachu, Jolteon |
| 220 | Espeon, Flareon, Leafeon |
| 250 | Mew (Queen), Raichu |
| 300 | Vaporeon |

**Note:** Leafeon's effective survivability is higher than its raw HP suggests due to its -40 damage reduction (see Section 11).

---

## 11. Eeveelution Changes

### 11.1 Quick Attack Retention
Vaporeon, Flareon, Leafeon, and Jolteon **retain Quick Attack (QA)** in addition to gaining their new typed move upon evolution. QA is not replaced. However, these eeveelutions **cannot combo QA with their enhanced movement pattern** — QA uses the same movement pattern as base Eevee (standard king adjacency) regardless of which eeveelution it is.

**Espeon is an exception — it does not retain Quick Attack.** Espeon's two attacks are Foresight and Psywave (see §11.5).

### 11.2 Flareon
- **Movement:** King adjacency + knight-jump movement (standard chess knight jump — can jump over intervening pieces).
- **New attack:** **Flare Blitz** — Fire attack dealing **180 damage**. Flareon takes **40 recoil damage** to itself after Flare Blitz resolves, regardless of whether the target was KO'd. Recoil can KO Flareon. Quick Attack has no recoil.
- **HP:** 220.

### 11.3 Vaporeon
- **Movement:** King adjacency + full rook movement (orthogonal, unlimited range).
- **HP:** 300 — the highest HP of any piece in the game.
- No additional special attack beyond QA retention.

### 11.4 Jolteon
- **Movement:** King adjacency + full Raichu movement pattern + **2-square diagonal jumps** (all four diagonal directions). Jolteon is strictly more mobile than Raichu.
- **Unobstructed movement:** All of Jolteon's extended moves (L-jumps, 2-square cardinals, 2-square diagonals) leap over any intervening pieces — they are never blocked by pieces occupying intermediate squares. This also applies to Raichu's 2-square cardinals, which are likewise unobstructed.
- **HP:** 200.

### 11.5 Espeon
- **Movement:** King adjacency + full queen movement (orthogonal and diagonal, unlimited range).
- **Attacks:** Foresight and Psywave. Espeon does **not** retain Quick Attack.
- **HP:** 220.
- **Note:** Standard queen-range ATTACK moves are removed from Espeon. Its only offensive options are Foresight (delayed single-target) and Psywave (AoE).

#### Psywave
- **Type:** Psychic. **Base damage:** 80.
- When Espeon uses Psywave, the attack radiates simultaneously along all 8 lines of queen movement (4 cardinal + 4 diagonal directions).
- In each direction, the wave travels until it hits the first obstacle (any Pokemon, Stealball, or Healball). It does **not** pass through obstacles.
- **Non-Psychic Pokemon (any piece except Mew and Espeon):** Takes damage equal to **80 − 10×n**, where **n** is the number of empty squares between Espeon and the target. Friend and foe are affected equally. Wave stops in that direction.
- **Psychic-type Pokemon (Mew and Espeon):** No damage. Wave stops in that direction.
- **Stealballs (Pokeball / Masterball) and Healballs (Safetyball / Master Safetyball):** No damage, not destroyed. Wave stops in that direction. Stealballs and Healballs are treated identically — they block the wave but are otherwise unaffected.
- **Minimum damage on this board:** 6 empty squares of separation → 80 − 60 = **20**.
- Psywave consumes Espeon's full turn (it cannot be combined with a MOVE action).

### 11.6 Leafeon
- **Movement:** King adjacency + full bishop movement (diagonal, unlimited range).
- **Passive:** **-40 damage reduction** applied to all incoming attacks, subtracted from the move's **base damage before type effectiveness modifiers are applied**. Has a floor of 1 (the reduced base cannot go below 1 before the multiplier is applied).
- **HP:** 220.

---

## 12. Foresight Visibility

- When a player uses Foresight (Mew or Espeon), the **opposing player is not told which square was targeted**. The opponent receives only the message that the opposing Mew or Espeon used Foresight this turn.
- The caster's player sees the targeted square normally (they chose it).
- The **piece identity** (Mew vs. Espeon) **is revealed** to the opponent, so they know which piece cast it and can infer the likely damage (both deal the same Foresight damage, but knowing which piece used it has positional implications).
- The target square remains hidden to the opponent until Foresight resolves. At resolution, the standard KO or damage is applied and the effect becomes visible to both players through the board state change.

---

## 13. Healball Rule Changes

### 13.1 Entry Restriction — Injured Pokemon Only
- Only **injured pokemon** (any pokemon below full HP) may enter a Healball.
- Healthy pokemon at full HP cannot enter a Healball under any circumstances.

### 13.2 Forward Entry Now Permitted for Injured Pokemon
- **Previous behavior:** An injured pokemon could not move forward into a Healball occupying the square directly ahead of it. The player was required to maneuver the pokemon to the side, or move the Healball forward or laterally to collect it.
- **New behavior:** An injured pokemon may now move forward directly into a Healball that occupies the square ahead of it. All other existing entry directions remain unchanged.

### 13.3 Master Healball — Immediate Full Heal
- **Previous behavior:** A Master Healball healed the stored pokemon at a rate of half its maximum HP per turn spent inside the ball.
- **New behavior:** A Master Healball **immediately restores the stored pokemon to full HP** at the moment of entry. The pokemon exits the ball at full HP regardless of how long it remains stored or when it is released.

---



### Tall Grass and Item System
- **Item initialization:** Remove all logic that assigns starting items to Pokemon by type. Replace with a randomized selection of 4 items from the pool of 5, always including the Thunderstone.
- **Board state:** Add a `tall_grass` layer to the middle 4 rows tracking: unexplored, explored-empty, or explored-with-item. This is separate from the `item` layer visible on explored squares.
- **Pokeball movement:** Confirm Pokeball movement logic does not trigger exploration or item pickup on any square.
- **Item visibility:** The item identity field should be tracked per-player: the holding player and the opposing player may have different knowledge states about what item is held. A traded or carried item's identity should only propagate to the opposing player when it is dropped onto the board.
- **Thunderstone rule** is currently hardcoded. If making this configurable in the future, expose as a `bool always_include_thunderstone` flag in game config.

### Healball Entry and Healing
- **Entry validation:** Add an HP check to all Healball entry logic — reject entry attempts from pokemon at full HP regardless of direction.
- **Forward entry:** Remove the existing restriction that blocked an injured pokemon from moving forward into a Healball occupying the square directly ahead of it. Forward entry should now be treated identically to lateral and diagonal entry for injured pokemon.
- **Master Healball heal timing:** Replace the per-turn half-HP heal logic with an immediate full HP restoration applied at the moment of entry. The stored pokemon's HP should be set to max HP on entry, not on release.

### Catch Rates
- Catch rate logic should branch on piece identity (Mew vs. all others) and then on current HP percentage against the three bins defined in Section 9.
- Master Stealball should bypass the HP bin logic entirely and resolve as 100% success.
- HP percentage thresholds are: full health (100%), half or above (50% ≤ HP < 100%), below half (HP < 50%).

### HP Values
- Update the HP initialization for all affected pieces to match the table in Section 10. These are the authoritative values going forward.
- Eeveelution HP values in Section 11 are the HP the piece spawns with upon evolution — they are not additive on top of Eevee's base HP.

### Eeveelution Movement and Abilities
- Each eeveelution's movement is the union of standard king adjacency plus its expanded pattern (rook, bishop, knight-jump, or Raichu pattern). QA uses only the king adjacency subset of that union, except for Espeon which does not have QA.
- **Espeon's move set:** MOVE (queen pattern), FORESIGHT, PSYWAVE, TRADE. Standard queen-range ATTACK moves are removed. Espeon cannot use Quick Attack.
- **Espeon's Psywave:** Implement as `ActionType.PSYWAVE`. The move has no explicit target — it fires from Espeon's position in all 8 directions simultaneously. In `_do_psywave`, walk each ray until the first obstacle: deal `max(10, 80 − 10×n)` to non-Psychic Pokemon; stop silently at Psychic-type Pokemon, Stealballs, and Healballs (no damage or destruction for any of these).
- **Flareon's Flare Blitz** (180 damage, FIRE type) should be implemented as a typed attack alongside QA. Apply 40 recoil damage to Flareon after the attack resolves. Knight-jump movement follows standard chess knight rules — it is not blocked by intervening pieces.
- **Leafeon's -40 damage reduction** should be subtracted from the attacker's base damage before the type effectiveness multiplier is applied. Enforce a floor of 1 on the post-reduction base (so the multiplier is applied to at least 1).
- **Jolteon's 2-square diagonal jumps** are unobstructed. **Raichu's 2-square cardinal slides** are also unobstructed — remove any intermediate-square obstruction check for both pieces.

### Foresight Visibility
- In `player_view_of_state`, when serializing the opponent's `pending_foresight`, mask the target coordinates. Include only enough information to display "[Mew / Espeon] used Foresight" — specifically the caster piece type (derivable from `caster_row` / `caster_col` in the full state). Do not include `target_row` or `target_col` in the masked output.
