# pokechess-app — FastAPI App Server

This directory contains the app server container (`pokechess-app`). It is the only service that touches Postgres. The MCTS engine container is called only for bot moves in PvB games.

## Before implementing anything, read these two docs

- **[`docs/pokechess_data_model.md`](../docs/pokechess_data_model.md)** — Full Postgres schema, canonical `games.state` and `games.move_history` JSON shapes, and the move lifecycle flow. This is the ground truth for every data structure the app touches.
- **[`docs/implementation_roadmap.md`](../docs/implementation_roadmap.md)** — Agreed architecture, container responsibilities, engine API contract, and the prioritized next-steps checklist for this service.

## What goes here

```
app/
  main.py              ← FastAPI app entrypoint, lifespan, middleware
  routes/
    games.py           ← POST /games, GET /games/{id}, POST /games/{id}/move
    legal_moves.py     ← GET /games/{id}/legal_moves
    users.py           ← auth, registration
    friends.py         ← friend requests, invites
  db/
    connection.py      ← asyncpg pool setup
    migrations/        ← Alembic migration files
    queries/           ← SQL query functions (one file per domain)
  engine_client.py     ← thin HTTP client for POST localhost:5001/move
```

## Key imports from shared engine

```python
from engine import GameState, get_legal_moves, apply_move, is_terminal
# GameState.from_dict(json) / GameState.to_dict() are the serialization boundary
```

The `engine/` package is copied into this container at build time (see `Dockerfile.app`). Do not add `bot/` or `cpp/` imports here — those are engine-container-only.
