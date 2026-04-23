PYTHON   := .venv/bin/python
UVICORN  := .venv/bin/uvicorn
PYTEST   := .venv/bin/pytest

# Load KEY=value pairs into Make and export to recipe shells (uvicorn, pytest, etc.)
-include .env
export

# Same names as docker-compose / .env; fall back if unset or empty
DB_USER := $(or $(POSTGRES_USER),pokechess)
DB_NAME := $(or $(POSTGRES_DB),pokechess)

.PHONY: partial full app frontend server-frontend schema bot-id test test-v down reset

# ---------------------------------------------------------------------------
# Partial integration testing (PvP only — no bot server required)
# ---------------------------------------------------------------------------
partial:
	docker compose up postgres -d
	@echo "Waiting for postgres to be healthy..."
	@until docker compose exec postgres pg_isready -U $(DB_USER) > /dev/null 2>&1; do sleep 1; done
	@$(MAKE) schema

# ---------------------------------------------------------------------------
# Full integration testing (PvP + PvB — requires bot/server.py to exist)
# ---------------------------------------------------------------------------
full:
	docker compose up --build -d
	@echo "Waiting for postgres to be healthy..."
	@until docker compose exec postgres pg_isready -U $(DB_USER) > /dev/null 2>&1; do sleep 1; done
	@$(MAKE) schema

# ---------------------------------------------------------------------------
# App / frontend — run in separate terminals (foreground processes)
# ---------------------------------------------------------------------------
app:
	$(UVICORN) app.main:app --reload --port 8000

# Builds the static export and serves it locally with SPA fallback, approximating
# S3/CloudFront behaviour (unknown paths → index.html). Use this to catch routing
# issues that only appear in the static build and not in the dev server.
frontend:
	cd frontend && npm run build && npx serve out -s

server-frontend:
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Schema — safe to re-run; errors on existing objects are non-fatal
# ---------------------------------------------------------------------------
schema:
	@echo "Applying schema..."
	docker compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) < app/db/schema.sql
	@echo "Schema applied."

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
bot-id:
	@echo "Metallic bot UUID:"
	@docker compose exec postgres psql -U $(DB_USER) -d $(DB_NAME) -t -c "SELECT id FROM bots WHERE name = 'Metallic';"

# ---------------------------------------------------------------------------
# Tests (no Docker needed)
# ---------------------------------------------------------------------------
test:
	$(PYTEST)

test-v:
	$(PYTEST) -v

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
down:
	docker compose down

reset:
	docker compose down -v
