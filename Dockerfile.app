# Dockerfile.app — pokechess-app (FastAPI app server)
# Builds: engine/ (shared game logic) + app/ (app server)
# Deliberately excludes bot/ and cpp/ — those are engine-container-only.

FROM python:3.12-slim

WORKDIR /app

# Copy only what this container needs
COPY engine/ ./engine/
COPY app/     ./app/

# Runtime deps
# Expand this list as app/ is implemented.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    asyncpg \
    alembic \
    "passlib[bcrypt]" \
    "python-jose[cryptography]"

# TODO (app backend): implement app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
