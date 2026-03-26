# PokeChess

A hybrid chess / Pokémon battle game. Two players command teams of Pokémon on a standard 8×8 board. Chess governs how pieces move — but each piece has **HP**, **type matchups**, and unique abilities that make every exchange matter.

![Starting Position](demo/board_preview.png)

*RED (Pikachu) deploys from rows 0–1. BLUE (Eevee) holds rows 6–7.*

---

## Try the Demo

Open **`demo/pokechess_demo.ipynb`** in Jupyter for an interactive walkthrough of all game mechanics: board layout, movement patterns, type-matchup combat, evolution, Foresight, stochastic Pokéball captures, and a fully **playable game** at the end.

```bash
pip install -r requirements.txt
jupyter notebook demo/pokechess_demo.ipynb
```

The playable section (Section 12) requires `ipympl` for click-to-move interaction:

```bash
pip install ipympl
```

---

## Rules Overview

### Pieces

| Piece | Chess Role | Type | HP | Special |
|---|---|---|---|---|
| **Pikachu** | Red King | Electric | 200 | Immune to Pokéballs; evolves into Raichu |
| **Eevee** | Blue King | Normal | 120 | Quick Attack (move + attack same turn); evolves into 5 forms |
| **Mew** | Queen | Psychic | 250 | 3 typed attacks (Fire Blast / Hydro Pump / Solar Beam) + Foresight |
| **Squirtle** | Rook | Water | 200 | Slides along ranks and files |
| **Charmander** | Knight | Fire | 160 | L-shaped jumps; leaps over pieces |
| **Bulbasaur** | Bishop | Grass | 160 | Slides diagonally |
| **Pokéball** | Pawn | — | — | 50 % capture chance on attack |
| **Masterball** | — | — | — | Guaranteed capture; Pokéball promotes here |

### Key Differences from Standard Chess

**HP and non-lethal attacks** — Pieces are not immediately removed on contact. An attacker stays put when the hit is non-lethal; the target only leaves the board when its HP reaches 0.

**Type matchups** — Every attack has a type. Water beats Fire, Fire beats Grass, Grass beats Water (2× / 0.5× damage). Same-type and off-triangle matchups deal 1×. Picking the right type often decides a fight.

**Stochastic captures** — Regular Pokéball attacks have a **50 %** chance to capture the target and a 50 % chance to fail (the target survives, full HP, and the Pokéball stays put). Masterballs always capture. Pikachu and Raichu are immune to all Pokéball capture attempts.

**Evolution** — Kings can evolve mid-game at the cost of a turn. Pikachu evolves into Raichu. Eevee evolves into one of five forms (Vaporeon, Flareon, Leafeon, Jolteon, Espeon) depending on which item it holds. Evolution restores HP equal to the difference in max HP between forms.

**Foresight** — Mew and Espeon can schedule a delayed attack targeting any square in their movement range. The damage resolves at the start of their *next* turn. Foresight cannot be used on consecutive turns.

**Free item trades** — Any piece can swap its held item with an adjacent teammate as a free action that does *not* end the turn. Trading an evolution stone to Eevee triggers an immediate auto-evolution and does consume the turn.

**No en passant. No castling.**

### Win Condition

Eliminate the opposing king. If both kings are eliminated on the same turn, the game is a draw. In timed play, the team with higher total HP wins (Pokéball = 50, Masterball = 200, all others = current HP).

---

## Project Structure

```
engine/     Core game logic — GameState, move generation, rule execution
bot/        MCTS bot — pure Monte Carlo, no neural network required
tests/      pytest test suite
demo/       Jupyter demo notebook + sprite cache
docs/       Rules PDF and piece-movement reference diagrams
cpp/        C++ hot-loop port via pybind11 (phase 3)
```

## Running Tests

```bash
pytest
```
