# Dockerfile.app — pokechess-app (FastAPI app server)
# Builds: engine/ (shared game logic) + app/ (app server)
# Deliberately excludes bot/ and cpp/ — those are engine-container-only.
# Schema is managed via app/db/schema.sql (applied manually or via CI); no Alembic.

FROM python:3.12-slim

WORKDIR /app

# Copy only what this container needs
COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY engine/ ./engine/
COPY app/     ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
