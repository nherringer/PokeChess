# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PokeChess is a hybrid chess/Pokemon game. This repo contains the ML bot (MCTS-based) only — a coworker owns the frontend and async layer separately.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_moves.py

# Run a single test
pytest tests/test_moves.py::test_name -v

# Win-rate benchmark (bot vs random, bot vs bot)
python scripts/benchmark.py                        # 20 games, 0.5s/move
python scripts/benchmark.py --budget 1.0 --games 50   # slower, more rigorous
```

No build step required for Python. The C++ extension is optional but strongly recommended for performance.

```bash
# Build C++ rollout extension (requires pybind11: pip install pybind11)
python setup.py build_ext --inplace

# The bot auto-detects the extension at import time; falls back to pure Python if not built.
```

## Architecture

```
engine/     Core game logic — no ML dependencies
  state.py    GameState, Piece, enums (PieceType, Team, Item, PokemonType)
  moves.py    Move dataclass + get_legal_moves(state) → List[Move]
  rules.py    apply_move() → [(state, prob)], is_terminal(), hp_winner()
  zobrist.py  Zobrist hashing for transposition table

bot/        MCTS bot — depends on engine, no frontend coupling
  mcts.py         MCTS tree, 4-phase loop, tree reuse between moves
  ucb.py          UCB1 formula with tunable exploration constant C
  transposition.py Persistent hash→(wins,visits) table across games

cpp/        C++ rollout engine (pybind11 bridge)
  engine.cpp    Full rollout hot-loop in C++; exposes run_rollouts() and run_rollout_with_rolls()
  state_codec.py  Python→wire-format encoder consumed by the C++ decoder
tests/      pytest — unit tests per module
scripts/    Standalone utilities (benchmark.py for win-rate validation)
docs/       Game design PDFs (rules, piece movement diagrams, board sheets)
```

## Key Design Decisions

**Algorithm:** Pure MCTS (no neural network for MVP). No training needed — runs at inference time. Time budget per move (default 3s) controls difficulty. Tree is reused between moves: when the bot plays move A and the opponent responds X, the A→X subtree is retained as the new root.

**Stochasticity:** Pokeball captures are coin flips (50%). `apply_move()` returns a list of `(state, probability)` pairs — usually one pair at p=1.0, two pairs for pokeball interactions. MCTS samples these during rollouts.

**Inter-game learning:** Transposition table (Zobrist hash → wins/visits) persists across games. Common positions accumulate statistics, giving warm-start priors.

**HP:** Always a multiple of 10. Zobrist hp_bucket = current_hp // 50.

**C++ move ordering:** `get_legal_moves` in C++ iterates the board in row-major order (not the `pieces[]` array). This matches Python's `all_pieces()` board iteration. If you change this to array-index order the fixed-roll tests will fail (different moves selected for the same roll).

## Game Rules Summary

See `docs/Rules.md` and `docs/PieceMovement.pdf` for full rules. Key points:
- Standard chess rules apply except no en passant, no castling
- Red (Pikachu) moves first. Blue (Eevee) moves second.
- Pieces have HP and typed moves. Attacker stays put unless it KOs the target.
- Attack range = movement range for all pieces.
- Type matchups: Water > Fire > Grass > Water (2x/1x/0.5x). Same type = 0.5x.
- Mew (Queen, Psychic, 250HP) has 4 moves and can always one-shot any starter.
- Eevee (Blue King, Normal, 120HP) can move + attack same turn (Quick Attack).
- Pikachu (Red King, Electric, 200HP) immune to regular pokeballs.
- Kings evolve mid-game: Pikachu→Raichu (costs a turn), Eevee→one of 5 evolutions.
- Foresight (Mew/Espeon): targets a square, resolves on caster's next turn. Can't use consecutively.
