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
- **Edge case — Foresight on a Stealball in tall grass:** Pokeballs cannot hold items, so no item interaction occurs. The vacated square remains unexplored tall grass.

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

---

## 9. Implementation Notes for Claude Code

- **Item initialization:** Remove all logic that assigns starting items to Pokemon by type. Replace with a randomized selection of 4 items from the pool of 5, always including the Thunderstone.
- **Board state:** Add a `tall_grass` layer to the middle 4 rows tracking: unexplored, explored-empty, or explored-with-item. This is separate from the `item` layer visible on explored squares.
- **Pokeball movement:** Confirm Pokeball movement logic does not trigger exploration or item pickup on any square.
- **Item visibility:** The item identity field should be tracked per-player: the holding player and the opposing player may have different knowledge states about what item is held. A traded or carried item's identity should only propagate to the opposing player when it is dropped onto the board.
- **Thunderstone rule** is currently hardcoded. If making this configurable in the future, expose as a `bool always_include_thunderstone` flag in game config.
