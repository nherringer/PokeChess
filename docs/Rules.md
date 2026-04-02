# PokeChess — Official Rules

*Current as of main branch*

---

## Table of Contents

1. [Overview](#1-overview)  
2. [The Board & Starting Layout](#2-the-board--starting-layout)  
3. [Piece Roster](#3-piece-roster)  
4. [Movement](#4-movement)  
5. [Combat](#5-combat)  
6. [Type Matchups](#6-type-matchups)  
7. [Special Abilities](#7-special-abilities)  
8. [Evolution](#8-evolution)  
9. [Items & Item Trading](#9-items--item-trading)  
10. [Pokéballs](#10-pokéballs)  
11. [Win Condition](#11-win-condition)  
12. [Omitted Chess Rules](#12-omitted-chess-rules)

---

## 1\. Overview

PokeChess is a two-player strategy game played on a standard 8×8 chess board. Chess governs how pieces move (mostly), but each piece has **HP**, **type matchups**, and **unique abilities** that transform every exchange into a Pokémon battle. Pieces are not immediately removed on contact — they absorb damage and only leave the board when their HP reaches zero.

**RED** (Pikachu) always moves first. **BLUE** (Eevee) moves second.

---

## 2\. The Board & Starting Layout

The board uses standard chess coordinates. RED deploys in rows 0–1; BLUE deploys in rows 6–7.

### Back row (row 0 for RED, row 7 for BLUE)

From left to right: **Squirtle — Charmander — Bulbasaur — King — Mew — Bulbasaur — Charmander — Squirtle**

(Kings: Pikachu for RED, Eevee for BLUE)

### Pawn row (row 1 for RED, row 6 for BLUE)

The pawn row is split by piece type based on column position:

- **Columns 0 and 7** (outer) — **Stealballs**  
- **Columns 1 and 6** (outer-middle) — **Stealballs**  
- **Columns 2 and 5** (inner-middle) — **Safetyballs**  
- **Columns 3 and 4** (inner) — **Safetyballs**

Each player starts with **4 Stealballs** and **4 Safetyballs**.

---

## 3\. Piece Roster

### Standard Pieces

| Piece | Chess Role | Team | Type | HP |
| :---- | :---- | :---- | :---- | :---- |
| Pikachu | King | RED | Electric | 200 |
| Eevee | King | BLUE | Normal | 120 |
| Mew | Queen | Both | Psychic | 250 |
| Squirtle | Rook | Both | Water | 200 |
| Charmander | Knight | Both | Fire | 200 |
| Bulbasaur | Bishop | Both | Grass | 200 |
| Stealball | Pawn (outer) | Both | — | — |
| Safetyball | Pawn (inner) | Both | — | — |

### Evolved Pieces

| Piece | Evolves From | Type | HP | Notes |
| :---- | :---- | :---- | :---- | :---- |
| Raichu | Pikachu | Electric | 250 | Requires Thunder Stone |
| Vaporeon | Eevee | Water | 220 | Requires Water Stone |
| Flareon | Eevee | Fire | 220 | Requires Fire Stone |
| Leafeon | Eevee | Grass | 220 | Requires Leaf Stone |
| Jolteon | Eevee | Electric | 220 | Requires Thunder Stone |
| Espeon | Eevee | Psychic | 220 | Requires Bent Spoon |
| Master Stealball | Stealball | — | — | Promoted upon reaching back rank |
| Master Safetyball | Safetyball | — | — | Promoted upon reaching back rank |

---

## 4\. Movement

All pieces move according to their chess role unless otherwise noted. **Attack range equals movement range** for all pieces — a piece attacks by moving onto an occupied enemy square.

### Squirtle (Rook)

Slides any number of squares horizontally or vertically. Cannot jump over pieces.

### Charmander (Knight)

Moves in an L-shape: 2 squares in one cardinal direction then 1 square perpendicular (or vice versa). **Can jump over pieces.**

### Bulbasaur (Bishop)

Slides any number of squares diagonally. Cannot jump over pieces.

### Mew (Queen)

Slides any number of squares in any direction (horizontal, vertical, or diagonal). Cannot jump over pieces.

### Pikachu (King)

Moves 1 square in any direction (standard King movement) **plus** additional knight-like "lightning bolt" L-jumps similar in pattern to Charmander (3,1 instead of 2,1). Can jump over pieces for the L-jump moves only.

### Raichu (King, evolved)

Moves 1 square in any direction (standard King movement) **plus** L-jumps (same as Pikachu) **plus** slides of up to 2 squares along any cardinal direction. The cardinal slides cannot jump over pieces.

### Eevee (King)

Moves 1 square in any direction (standard King movement). See also: **Quick Attack** in Section 7\.

### Eevee Evolutions (King)

| Evolution | Movement |
| :---- | :---- |
| Vaporeon | 1 square in any direction (King) \+ full rook sliding in all cardinal directions |
| Flareon | 1 square in any direction (King) \+ knight-style L-jumps |
| Leafeon | 1 square in any direction (King) \+ full bishop sliding in all diagonal directions |
| Jolteon | 1 square in any direction (King) \+ extended L-jumps \+ 2-square cardinal slides (same as Raichu) |
| Espeon | 1 square in any direction (King) \+ full queen sliding in all directions |

### Stealball & Safetyball (Pawns)

Both ball types share the same movement pattern:

- Up to **2 squares forward** (toward the opponent's back rank)  
- Up to **2 squares laterally** (left or right, no forward/backward component)  
- **1 square diagonally forward**

Stealballs and Safetyballs **cannot move backward**.

### Master Stealball & Master Safetyball (Promoted Pawns)

Both master variants use the full omnidirectional mirror of the basic ball pattern:

- Up to **2 squares forward or backward**  
- Up to **2 squares laterally**  
- **1 square diagonally in any direction**

---

## 5\. Combat

### Non-Lethal Attacks

When a piece attacks an enemy and the hit is non-lethal (the target's HP does not reach zero), **the attacker stays on its original square** and the target remains on its square with reduced HP. A piece is only removed from the board when its HP reaches zero.

### Damage

Base damage values are determined by piece type. Actual damage is modified by type matchups (see Section 6). **Attack range equals movement range** — a piece can attack any square it could legally move to.

### HP

All HP values are multiples of 10\. A piece at any HP above zero remains on the board and fully functional.

---

## 6\. Type Matchups

Each piece has a type (or no type, in the case of Pokéballs). When a piece attacks, the damage is multiplied based on the matchup between the **attack move type** and the **defender's type**:

| Attack Move → Defender | Multiplier |
| :---- | :---- |
| Water → Fire | 2× |
| Fire → Grass | 2× |
| Grass → Water | 2× |
| Fire → Water | 0.5× |
| Grass → Fire | 0.5× |
| Water → Grass | 0.5× |
| Same type | 0.5× |
| All other matchups | 1× |

The type triangle is: **Water beats Fire, Fire beats Grass, Grass beats Water.**

Mew has access to three typed moves — Fire Blast (Fire), Hydro Pump (Water), and Solar Beam (Grass) — in addition to its base Psychic type. This means Mew can always exploit a type advantage against any starter piece and can always one-shot any of them with the correct move.

---

## 7\. Special Abilities

### Quick Attack (Eevee)

Eevee may **attack and move in the same turn**, in either order.

- **Attack then move:** If the attack KOs the target, Eevee's movement begins from the target's (now vacated) square. If the target survives, Eevee moves from its original square.  
- **Move then attack:** Eevee moves first, then attacks from its new position.

### Foresight (Mew and Espeon)

The caster designates any square within its movement range as a **Foresight target**. No immediate damage occurs. At the **start of the caster's next turn**, the damage resolves against whatever piece occupies that square at that moment (if any).

- Foresight **cannot be used on consecutive turns** — the caster must take at least one non-Foresight turn between uses.  
- If the targeted square is empty when the damage resolves, nothing happens.

---

## 8\. Evolution

Kings may evolve **mid-game at the cost of one full turn**. The evolving King does not move or attack that turn. Evolution grants higher max HP, upgraded movement, and (for Eevee evolutions) a new type.

**HP restoration on evolution:** The evolving piece's current HP increases by the difference between the evolved form's max HP and the base form's max HP. Example: Pikachu at 150 HP evolving into Raichu (max 250\) gains 50 HP, ending at 200\.

### Pikachu → Raichu

- Raichu gains \+50 max HP, expanded movement (cardinal slides).  
- Raichu loses Stealball immunity but gains the ability to be stored and healed by Safetyballs.

### Eevee → Eeveelution

- Requires the appropriate held item (evolution stone).  
- All five evolutions gain \+100 max HP and a new type. Each has a distinct movement pattern (see Section 4).  
- Espeon gains the Foresight ability upon evolving.

---

## 9\. Items & Item Trading

Some pieces begin the game holding an **evolution stone** (used to trigger Eevee's evolution). Items can be passed between allied pieces during play.

### Trading Rules

- Any **non-pawn** piece may swap its held item with an adjacent allied piece as a **free action** that does **not** end the turn.  
- **Pawns (Stealballs and Safetyballs) cannot hold or trade items.**

---

## 10\. Pokéballs

Pokéballs are the pawn pieces of PokeChess, divided into two distinct types with different roles.

### 10.1 Stealballs

Stealballs are the **offensive** pawn type. They occupy the outer columns (0, 1, 6, 7\) of each player's pawn row.

**Movement:** Up to 2 squares forward, up to 2 squares laterally, or 1 square diagonally forward. Cannot move backward.

**Attack:** When a Stealball moves onto a square occupied by an enemy piece, a capture attempt is made:

- **50% chance:** The target is captured and removed from the board. The Stealball is also removed (spent).  
- **50% chance:** The attempt fails. The target survives at its current HP and the Stealball is removed from the board.

**Restrictions:**

- Stealballs **cannot** target other pawns (Stealballs or Safetyballs).  
- Stealballs **cannot** target Pikachu. Pikachu is immune to all Stealball capture attempts.  
- Raichu (evolved Pikachu) is **not** immune — it can be captured by a Stealball.  
- Stealballs cannot hold items.

**Promotion:** A Stealball that reaches the opponent's back rank promotes to a **Master Stealball**.

---

### 10.2 Master Stealball

**Movement:** Full omnidirectional ball pattern — up to 2 squares in any cardinal direction, or 1 square diagonally in any direction.

**Attack:** Guaranteed capture of the target. No RNG. The Master Stealball is removed after a successful capture (spent).

**Restrictions:** Same as Stealball — cannot target pawns, cannot hold items.

---

### 10.3 Safetyballs

Safetyballs are the **defensive** pawn type. They occupy the inner columns (2, 3, 4, 5\) of each player's pawn row.

**Movement:** Up to 2 squares forward, up to 2 squares laterally, or 1 square diagonally forward. Cannot move backward. A Safetyball may only move onto an **empty square** or a square occupied by an **injured allied Pokémon** (any ally below max HP). It can never move onto an enemy square.

**Storing an ally:** When a Safetyball moves onto a square occupied by an injured ally, that Pokémon is **automatically stored** inside the Safetyball. The stored Pokémon is removed from the board; the Safetyball remains on that square representing both pieces. Storage is not optional — any legal move onto an injured ally triggers it automatically.

**Storage constraint:** A Safetyball may only store a Pokémon if the player has **at least one other piece remaining on the board** at the time of storage. A player may not reduce their board presence to zero pieces.

**Healing:** While a Pokémon is stored, it heals **¼ of its maximum HP per turn** that the Safetyball moves (i.e. starts and ends its turn on different squares). Healing does not accrue on a turn where the Safetyball does not move.

**Releasing a stored Pokémon:** Release occurs when any one of the following triggers:

| Trigger | Description |
| :---- | :---- |
| **Full HP** | The stored Pokémon reaches its maximum HP at the end of a turn. Automatic. |
| **No movement** | The player chooses not to move the Safetyball (it starts and ends its turn on the same square). Automatic. |
| **Player choice** | The player may voluntarily release the Pokémon at the start of any of their turns. |

On release: the stored Pokémon is placed on the square the Safetyball currently occupies, the Safetyball is removed from the board, and the released Pokémon is **not available to move until the player's next turn**.

**Immunity:** Safetyballs **cannot be attacked or captured** by the opponent under any circumstances, whether or not they are carrying a stored Pokémon. Enemy pieces may not move onto a Safetyball's square.

**Restrictions:**

- Safetyballs **cannot store Pikachu**. Pikachu cannot benefit from Safetyball healing under any circumstances. Raichu (evolved Pikachu) **can** be stored and healed normally.  
- Safetyballs cannot hold items.

**Promotion:** A Safetyball that reaches the opponent's back rank promotes to a **Master Safetyball**.

---

### 10.4 Master Safetyball

**Movement:** Full omnidirectional ball pattern — up to 2 squares in any cardinal direction, or 1 square diagonally in any direction.

**Healing rate:** ½ of the stored Pokémon's maximum HP per moving turn (instead of ¼).

**All other Safetyball rules apply:** same storage constraint, same release triggers, same Pikachu restriction, same immunity to attack, no items.

---

### 10.5 Pikachu & Raichu — Pokéball Interaction Summary

|  | Pikachu | Raichu |
| :---- | :---- | :---- |
| Immune to Stealball capture | ✅ Yes | ❌ No (50% capture rate applies) |
| Can be stored by Safetyball | ❌ No | ✅ Yes |

This asymmetry is the core trade-off of the Pikachu evolution decision. Pikachu is untouchable by Pokéballs but cannot be healed through storage. Raichu becomes vulnerable to Stealballs but gains access to Safetyball recovery.

---

## 11\. Win Condition

**Eliminate the opposing King.** A King is eliminated when its HP reaches zero.

- In **timed play**, if time expires before a King is eliminated, the team with higher **total HP** wins. HP totals are calculated as:  
  - Stealball/Safetyball: 50  
  - Master Stealball/Safetyball: 200  
  - All other pieces: current HP  
  - Stored Pokémon HP counts toward the total.

---

## 12\. Omitted Chess Rules

The following standard chess rules **do not apply** in PokeChess:

- **No en passant**  
- **No castling**  
- **No check or checkmate** — the King is not in a special threatened state; it must be reduced to 0 HP to be eliminated  
- **No stalemate** — if a player has no legal moves, they lose their turn  
- **No draw by repetition or insufficient material**

