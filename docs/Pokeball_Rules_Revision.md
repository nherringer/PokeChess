# PokeChess — Pokéball Rules Revision
*Draft v0.4*

> **Status:** Proposed revision. Supersedes the Pokéball and Masterball rules in `docs/Rules.pdf` if adopted. The CLAUDE.md rules summary will also need updating.

| Version | Changes |
|---------|---------|
| v0.4 | Corrected forward movement for all four ball types: basic balls can move up to 2 squares forward (not 1); master balls mirror this with up to 2 squares backward. |
| v0.3 | Corrected movement for all four ball types per PieceMovement.pdf: basic balls move up to 2 sq laterally, 1 sq forward, or 1 sq diagonally forward (not 1 sq forward only); master balls use full omnidirectional mirror of that pattern (not queen-like sliding). Replaced Section 4.5 — Safetyballs cannot be attacked or captured at all (previously incorrectly stated they could be captured). Updated summary table accordingly. |
| v0.2 | Clarified King storage: Kings (except Pikachu) may be stored provided the board constraint is met. Corrected "no movement" auto-release: triggers when the player chooses not to move the Safetyball, not when movement is physically blocked. |
| v0.1 | Initial draft. |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Piece Roster Changes](#2-piece-roster-changes)
3. [Stealball (formerly Pokéball)](#3-stealball-formerly-pokéball)
4. [Safetyball](#4-safetyball)
5. [Master Stealball (formerly Masterball)](#5-master-stealball-formerly-masterball)
6. [Master Safetyball](#6-master-safetyball)
7. [Starting Configuration](#7-starting-configuration)
8. [Pikachu & Raichu Interaction](#8-pikachu--raichu-interaction)
9. [Rules Summary Table](#9-rules-summary-table)
10. [Open Questions](#10-open-questions)

---

## 1. Overview

This revision splits the pawn row into two distinct Pokéball types: **Stealballs** and **Safetyballs**. Each player starts with four of each. The stealball preserves the original Pokéball's offensive capture mechanic. The safetyball introduces a new defensive healing-and-storage mechanic, allowing injured allied Pokémon to be temporarily withdrawn from the board to recover HP.

Together these changes add a triage and positioning layer to the game: players must now decide not only how to attack but when to pull a damaged piece off the board, how long to keep it in storage, and how to protect the safetyball carrying it.

---

## 2. Piece Roster Changes

| Old Name | New Name | Count | Role |
|----------|----------|-------|------|
| Pokéball | Stealball | 4 | Offensive pawn — captures enemy pieces |
| *(new)* | Safetyball | 4 | Defensive pawn — stores and heals allied pieces |
| Masterball | Master Stealball | — | Promoted Stealball |
| *(new)* | Master Safetyball | — | Promoted Safetyball |

Each player's pawn row now consists of 4 Stealballs and 4 Safetyballs. See [Section 7](#7-starting-configuration) for placement.

---

## 3. Stealball (formerly Pokéball)

All existing Pokéball rules carry over unchanged:

- Can move to any of the following squares: **up to 2 squares laterally** (left or right, staying on the same rank), **up to 2 squares forward**, or **1 square diagonally forward**. Cannot move backward. These are discrete target squares, not a slide.
- **Attack:** Moves onto a square occupied by an enemy piece. 50% chance to capture (remove from board); 50% chance to fail (enemy survives at full HP, Stealball remains in place).
- Can only move to empty squares or squares occupied by enemy pieces.
- **Promotion:** Upon reaching the back rank, promotes to a **Master Stealball** (see Section 5).
- **Pikachu/Raichu immunity:** Pikachu and Raichu cannot be captured by a Stealball. A Stealball attack on Pikachu or Raichu always fails; the Stealball remains in place.

---

## 4. Safetyball

### 4.1 Movement

Safetyballs follow the same movement rules as Stealballs — up to 2 squares laterally, up to 2 squares forward, or 1 square diagonally forward; no backward movement — except that they may only move onto:

- An **empty square**, or
- A square occupied by an **injured allied Pokémon** (any allied piece below max HP, including the King — see constraint in Section 4.4).

A Safetyball may never move onto a square occupied by an enemy piece and has no offensive capability of any kind.

### 4.2 Storing a Pokémon

When a Safetyball moves onto a square occupied by an injured allied Pokémon, that Pokémon is **automatically stored** inside the Safetyball. The stored Pokémon is removed from the board; the Safetyball now occupies that square and represents both pieces. Storage is not optional — any legal move onto an injured ally triggers it.

**Constraint:** A Safetyball may only store a Pokémon if the player has **at least one other Pokémon remaining on the board** at the time of storage (not counting the Safetyball itself). A player may not store a piece if doing so would leave no other pieces on the board. Note that the King may be stored like any other piece provided this constraint is met — the one exception being Pikachu, who cannot be stored under any circumstances (see Section 8).

Only **one Pokémon** may be stored in any given Safetyball at a time.

### 4.3 Healing

While a Pokémon is stored, it heals **¼ of its maximum HP per turn** that the Safetyball moves (i.e. starts and ends its turn on different squares). Healing accrues at the end of each such turn. HP cannot exceed the Pokémon's maximum.

Healing does **not** accrue on a turn where the Safetyball does not move (starts and ends on the same square).

### 4.4 Releasing a Pokémon

A stored Pokémon is released — and the Safetyball is removed from the board — when **any one** of the following conditions is met:

| Trigger | Description |
|---------|-------------|
| **Full health** | The stored Pokémon's HP reaches its maximum at the end of a turn. Release is automatic. |
| **No movement** | The Safetyball starts and ends its turn on the same square (the player chose not to move it). Release is automatic. |
| **Player choice** | The player may voluntarily release the Pokémon at the start of any of their turns before moving the Safetyball. |

In all cases: the stored Pokémon is placed on the square the Safetyball currently occupies, the Safetyball is removed from the board, and the released Pokémon is **not available to move until the player's next turn**.

### 4.5 Safetyball Immunity

Safetyballs **cannot be attacked or captured** by the opponent under any circumstances, regardless of whether they are carrying a stored Pokémon. Enemy pieces may not move onto a Safetyball's square. This immunity applies equally to Master Safetyballs.

---

## 5. Master Stealball (formerly Masterball)

All existing Masterball rules carry over unchanged:

- Reached by promoting a Stealball upon reaching the back rank.
- Can move to any square reachable by the basic Stealball pattern **plus the full mirror of that pattern in reverse** — i.e. up to 2 squares laterally, up to 2 squares forward or backward, and 1 square diagonally in any direction. Fully omnidirectional within that same discrete pattern.
- **Attack:** Guaranteed capture of any enemy piece. No RNG.
- **Pikachu/Raichu immunity** still applies — a Master Stealball attack on Pikachu or Raichu still fails.

---

## 6. Master Safetyball

Reached by promoting a Safetyball upon reaching the back rank.

- Moves using the same omnidirectional pattern as the Master Stealball — up to 2 squares laterally, up to 2 squares forward or backward, and 1 square diagonally in any direction.
- Retains full Safetyball storage and healing mechanics.
- **Heals ½ of the stored Pokémon's maximum HP per turn** (instead of ¼).
- Has **no offensive capability** — cannot move onto or attack enemy pieces under any circumstances.
- **Cannot be attacked or captured** by the opponent, whether or not it is carrying a stored Pokémon.
- All release rules from Section 4.4 apply unchanged.

---

## 7. Starting Configuration

Each player begins with 4 Stealballs and 4 Safetyballs in their pawn row (row 1 for Red, row 6 for Blue). The arrangement of the two types within that row is an **open design decision** with three candidate approaches:

- **Fixed pattern** — a predetermined alternating or grouped layout (e.g. SSBB BBSS or SBSB SBSB) that is identical for both players. Predictable; easier to learn.
- **Random** — positions are randomised at game start (both players see the layout before play begins). Adds variety; may create uneven matchups.
- **Player-chosen** — each player secretly arranges their 4 Stealballs and 4 Safetyballs before the game, then both are revealed simultaneously. Adds a pre-game strategy layer analogous to piece placement variants.

See [Open Questions](#10-open-questions).

---

## 8. Pikachu & Raichu Interaction

This revision updates the Pikachu/Raichu special rules to account for both ball types.

### Pikachu
- **Immune to Stealballs** (unchanged) — Stealball and Master Stealball attacks always fail against Pikachu.
- **Cannot be stored by Safetyballs** — Safetyballs may not move onto Pikachu's square. Pikachu cannot benefit from Safetyball healing under any circumstances.

### Raichu (evolved Pikachu)
- **Not immune to Stealballs** — Raichu can be captured by a Stealball (50% chance) or guaranteed-captured by a Master Stealball. This is the trade-off for evolving.
- **Can be stored by Safetyballs** — Raichu may be stored and healed normally. This is Raichu's compensating advantage over Pikachu.

### Design Rationale
The Pikachu ↔ Raichu evolution decision is now a genuine strategic trade-off:

| | Pikachu | Raichu |
|-|---------|--------|
| Stealball immunity | ✅ Yes | ❌ No |
| Safetyball healing | ❌ No | ✅ Yes |
| Evolution cost | — | 1 turn |

A player sitting on low HP with Pikachu cannot fall back on Safetyball recovery — they must either evolve (losing immunity, gaining healability) or protect a vulnerable King through positioning alone.

---

## 9. Rules Summary Table

| Rule | Stealball | Safetyball | Master Stealball | Master Safetyball |
|------|-----------|------------|------------------|-------------------|
| Movement | Up to 2 sq lateral, up to 2 sq forward, 1 sq diag-forward | Up to 2 sq lateral, up to 2 sq forward, 1 sq diag-forward | Omnidirectional: same pattern + full backward mirror | Omnidirectional: same pattern + full backward mirror |
| Valid target squares | Empty or enemy | Empty or injured ally | Empty or enemy | Empty or injured ally |
| Offensive capability | Yes (50% capture) | None | Yes (guaranteed capture) | None |
| Storage capability | None | 1 allied piece | None | 1 allied piece |
| Heal rate (per moving turn) | — | ¼ max HP | — | ½ max HP |
| Auto-release on no movement | — | Yes | — | Yes |
| Auto-release on full HP | — | Yes | — | Yes |
| Can be attacked/captured | Yes | **No** | Yes | **No** |
| Pikachu can be stored | — | No | — | No |
| Raichu can be stored | — | Yes | — | Yes |

---

## 10. Open Questions

- [ ] **Starting configuration** — fixed pattern, random, or player-chosen? If fixed, what pattern? (See Section 7.)
- [ ] **Eevee interaction** — Eevee's Quick Attack lets it move and attack in the same turn. Can Eevee move into a Safetyball's square (triggering storage) as part of a Quick Attack turn? Clarification needed.
- [ ] **Foresight interaction** — if a Foresight attack is scheduled against a piece that is subsequently stored in a Safetyball before the damage resolves, what happens? Options: damage applies to the Safetyball, damage is cancelled, or damage applies to the stored piece directly.
- [ ] **Campaign integration** — do Safetyball captures count toward the starter evolution thresholds defined in `docs/CampaignDesign.md`? (Storing an ally is not a capture, so likely no — but worth confirming.)
