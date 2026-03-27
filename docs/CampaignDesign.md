# PokeChess — Solo Campaign Design Document
*Draft v0.1*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Pillars](#2-design-pillars)
3. [Starter Sets](#3-starter-sets)
4. [Campaign Progression](#4-campaign-progression)
5. [The Rival](#5-the-rival)
6. [Team Alpha](#6-team-alpha)
7. [Persistent Progression](#7-persistent-progression)
8. [Campaign Save Format](#8-campaign-save-format-sketch)
9. [Open Questions & Future Work](#9-open-questions--future-work)

---

## 1. Overview

The PokeChess Solo Campaign adapts the classic Pokémon game formula into a series of PokeChess battles with persistent progression. The player selects a starter set, travels through eight gym towns, contends with the villainous Team Alpha, and faces a recurring rival — all resolved through PokeChess games whose outcomes feed a cross-battle stat tracker.

This document defines the campaign structure, rules expansions, and design rationale. Implementation details (save format, UI) are out of scope here.

---

## 2. Design Pillars

The campaign is designed to capture the elements that made the original Pokémon games iconic:

- **Personal identity** — your starter set defines your playstyle and your story from the first choice.
- **Sense of growth** — starters visibly evolve as your campaign record improves, rewarding consistent play.
- **Structured tension** — gyms provide predictable progression checkpoints; Team Alpha and the rival layer in surprise and narrative momentum.
- **Type literacy** — each gym forces the player to confront a specific type matchup, gradually teaching the full type triangle.
- **Rival as mirror** — the rival starts on equal footing and grows alongside the player, making each rematch meaningful.

---

## 3. Starter Sets

### 3.1 The Choice

At the start of the campaign, Professor Pine presents the player with three PokeChess sets. Each set has a unique King and Queen with different types, HP values, and special abilities. The player chooses one; the rival then picks one of the two remaining sets (the third belongs to a late-game NPC).

The Rooks (Squirtle), Knights (Charmander), and Bishops (Bulbasaur) are identical across all three sets. Only the King and Queen differ.

### 3.2 Open Design Question — Set Identity

The specific Pokémon that make up the three King/Queen pairs is one of the most consequential design decisions in the campaign. Several directions are worth considering before locking this in:

#### Option A — Extend the Base Game
Keep Pikachu and Eevee as two of the three Kings, preserving the base game's identities, and introduce a third King alongside two new Queen alternatives to Mew — perhaps Celebi or Jirachi. This direction minimises rules delta from the base game and will feel immediately familiar to returning players.

#### Option B — Three Entirely New Trifectas
Replace all three King/Queen pairs with brand-new Pokémon, chosen to form a clean type triangle — similar to how the original Fire/Grass/Water starters created balanced rivalry. The type triangle doesn't have to mirror the base game. Some candidate triangles:

- **Psychic / Dark / Fighting** — mirrors the in-game type triangle where Fighting beats Dark, Dark beats Psychic, and Psychic beats Fighting.
- **Flying / Fighting / Rock** — a more physical triangle with strong movement-style flavour.
- **Ghost / Normal / Fairy** — a thematic triangle built around immunity interactions.

This direction gives the campaign a fully distinct identity from the base game and makes the starter choice feel genuinely fresh.

#### Option C — Hybrid
Keep one iconic Pokémon (e.g. Eevee, given its rich evolution tree) as one King, and build the other two slots around a new type triangle. This preserves a familiar anchor while still introducing new identities.

### 3.3 Temporary In-Battle Evolution

Kings in the campaign gain a new mechanic: **temporary in-battle evolution**. At the cost of one turn, the King may evolve into a more powerful form for the remainder of that game. This evolution:

- Increases the King's max HP and base attack damage for the duration of the battle.
- Grants access to one additional or upgraded special ability.
- **Reverts fully after the game ends** — it does not affect the campaign's persistent stat record.
- Can only be used once per game.

The Queen pieces also gain campaign-specific identities distinct from Mew. Their special abilities should feel thematically paired with their King, and they too may have a single temporary upgrade available mid-battle. Exact Queen designs are TBD pending the starter set direction chosen above.

---

## 4. Campaign Progression

### 4.1 Structure

The campaign follows a linear structure modelled on the classic eight-gym Pokémon formula. The player moves town to town, battling gym leaders, encountering Team Alpha, and periodically facing the rival. Each node on the map is resolved by playing a PokeChess game.

Rough battle count per playthrough: ~8 gyms + ~6 rival battles + ~6 Team Alpha encounters + optional rematches = **~20–25 games**.

### 4.2 Gym Progression

Each gym leader specialises in a single type. Their board is composed of pieces whose attack types match that specialisation, making type matchup awareness the central skill the gym tests.

| # | Town | Type | Difficulty | Notes |
|---|------|------|------------|-------|
| 1 | Rustpetal Town | Grass | Easy | Bulbasaur-line advantage; intro to type matchups |
| 2 | Coalstone City | Rock | Easy | Defense-heavy opponent; patience rewarded |
| 3 | Cinderport City | Fire | Medium | Squirtle-line shines; first appearance of Charmander counters |
| 4 | Tidemark City | Water | Medium | Mid-campaign check; rival battle follows immediately after |
| 5 | Voltspire City | Electric | Medium | Fast, aggressive style; Foresight becomes critical |
| 6 | Mirefall Town | Poison | Hard | Status-adjacent pressure; Team Alpha subplot peaks here |
| 7 | Frostholm City | Ice | Hard | Defensive glacial style; evolution thresholds likely hit |
| 8 | Shadowpeak City | Psychic | Hard | Final gym; Mew-class queen tactics; Team Alpha climax |

Gym leaders do not use evolved Squirtle/Charmander/Bulbasaur lines. Their boards are fixed. The player's persistent evolutions are therefore an asymmetric advantage that rewards long campaign play.

---

## 5. The Rival

### 5.1 Role

The rival is introduced in the hometown immediately after the player makes their starter choice. They are upbeat, competitive, and genuinely skilled — not a villain, but a peer who grows in parallel with the player. Their arc should echo classic Pokémon rivals: early overconfidence, mid-campaign self-doubt (especially during the Team Alpha storyline), and a final reckoning at the Championship.

### 5.2 Rival Battle Schedule

| Encounter | Difficulty | Notes |
|-----------|------------|-------|
| 1 — Hometown | Tutorial | After choosing your set; rival picks one of the remaining two |
| 2 — After Gym 2 | Easy | Rival's starters have evolved to Stage 2 if they hit the threshold |
| 3 — After Gym 4 | Medium | Rival uses Foresight for the first time; stakes escalate |
| 4 — After Gym 6 | Medium | Team Alpha has corrupted one of rival's pieces (thematic only) |
| 5 — After Gym 8 | Hard | Pre-Championship showdown; rival at full evolution |
| 6 — Championship | Very Hard | Optional final rival battle; determines canonical ending |

### 5.3 Set Selection

The rival picks their set immediately after the player. If the player chose Set A, the rival picks randomly from Sets B and C (weighted toward the harder matchup to create tension). The third set is held by a late-game NPC — a champion or mentor figure who uses it in an optional bonus battle.

The rival's starters evolve on the same capture-threshold rules as the player's — their campaign record is simulated between encounters to keep difficulty scaling realistic.

---

## 6. Team Alpha

### 6.1 Concept

Team Alpha is the campaign's antagonist faction. Their goal — to be fleshed out in a narrative pass — should involve exploiting or corrupting the PokeChess game itself (e.g. tampering with Pokéball capture rules, or attempting to seize legendary pieces). Their boards are chaotically assembled, favouring aggressive or unpredictable play.

### 6.2 Encounter Schedule

| # | When | Opponent | Story Beat |
|---|------|----------|------------|
| 1 | Between Gym 1–2 | Grunt Pair | Introduction to Team Alpha; low stakes, two weak boards |
| 2 | Between Gym 2–3 | Grunt Trio | First hint of Alpha's plan; threaten a town's resources |
| 3 | Between Gym 3–4 | Admin: Vega | First named villain; mid-difficulty; Foresight used against you |
| 4 | Between Gym 5–6 | Admin: Lyra | Alpha's plan revealed; hardest admin fight yet |
| 5 | Between Gym 6–7 | Alpha Commander | The true scope of the plan; evolved grunt boards |
| 6 | After Gym 8 | Team Alpha Boss | Climactic final villain battle before the Championship |

Admin and Commander boards are harder than same-numbered gym leaders. Grunt boards are intentionally easier — they serve as breathing room and story delivery. Beating an Alpha encounter does not yield persistent stat bonuses but may unlock cosmetic rewards or lore entries.

---

## 7. Persistent Progression

### 7.1 Stat Tracking

After each game (win or loss), the following stats are written to the campaign save:

- Captures made by each piece this game (increments lifetime capture counter).
- HP remaining for each piece at game end (cosmetic record only; all pieces start at full HP next game).
- Win/loss result and opponent identity.

### 7.2 Permanent Evolution of Starters

The three starter Pokémon (Charmander, Bulbasaur, Squirtle) evolve permanently when their lifetime capture count crosses a threshold. These evolutions are tracked in the campaign save and persist across all future games.

| Pokémon | Role / Move | Stage 2 (5 captures) | Stage 3 (10 captures) | Stat Change |
|---------|-------------|----------------------|-----------------------|-------------|
| Charmander | Fire / Knight | Charmeleon | Charizard | +40 HP per stage; base attack damage +5 per stage |
| Bulbasaur | Grass / Bishop | Ivysaur | Venusaur | +40 HP per stage; base attack damage +5 per stage |
| Squirtle | Water / Rook | Wartortle | Blastoise | +40 HP per stage; base attack damage +5 per stage |

Additional rules:

- **Movement patterns do not change on evolution** — Charizard still moves like a Knight, Venusaur like a Bishop, Blastoise like a Rook.
- Evolution is announced **between games**, not mid-battle. The next game begins with the evolved form already on the board.
- If a piece is captured before it reaches its evolution threshold, its capture count is retained — captures are cumulative even across losses.
- The rival's starters evolve on the same thresholds (simulated); their board reflects this at each encounter.

### 7.3 Future Progression Hooks

The following are flagged as potential future expansions to the progression system:

- **Item system** — held items found or purchased between battles that modify piece behaviour (e.g. a Charcoal item that boosts Fire-type attack damage by 25%).
- **Badge bonuses** — winning a gym badge grants a small permanent campaign-wide buff (e.g. all Grass-type attacks deal +10% damage after the Grass gym badge).
- **Team Alpha drops** — defeating an Admin unlocks a one-use special piece (e.g. a Ditto piece that copies the movement type of any adjacent friendly piece for one turn).

---

## 8. Campaign Save Format (Sketch)

The save file needs to track at minimum:

```json
{
  "starter_set": 0,
  "rival_set": 1,
  "badges": [false, false, false, false, false, false, false, false],
  "captures": { "charmander": 0, "bulbasaur": 0, "squirtle": 0 },
  "evolutions": { "charmander": 0, "bulbasaur": 0, "squirtle": 0 },
  "rival_captures": { "charmander": 0, "bulbasaur": 0, "squirtle": 0 },
  "rival_evolutions": { "charmander": 0, "bulbasaur": 0, "squirtle": 0 },
  "alpha_progress": 0,
  "game_log": [
    { "opponent": "Gym 1 — Rustpetal", "result": "win", "captures_this_game": { "charmander": 2, "bulbasaur": 1, "squirtle": 0 } }
  ]
}
```

Format is JSON. A Python dataclass in `engine/campaign_state.py` would be the natural home for this, mirroring the structure of `engine/state.py`.

---

## 9. Open Questions & Future Work

- [ ] Finalise starter set direction (see Section 3.2) before any implementation begins.
- [ ] Name the rival, gym leaders, and Team Alpha admins/boss.
- [ ] Write narrative text for Professor Pine's introduction and each gym/Alpha encounter.
- [ ] Define exact HP and attack damage values for evolved King forms.
- [ ] Decide whether losses to gyms or Team Alpha have consequences (e.g. forced rematch, no consequence, or a small stat penalty).
- [ ] Decide on a Championship structure after Gym 8 — an Elite Four equivalent, or straight to the rival final?
- [ ] Scope the item system and badge bonuses for v1 vs. later phases.

---

*PokeChess Campaign Design Document — Draft v0.1*
