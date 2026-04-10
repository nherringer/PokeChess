import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://pokechess:pokechess@localhost:5432/pokechess"
)
ENGINE_URL: str = os.environ.get("ENGINE_URL", "http://localhost:5001")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
ALGORITHM: str = "HS256"


def asyncpg_dsn() -> str:
    """Convert DATABASE_URL to a raw asyncpg-compatible DSN."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def sync_dsn() -> str:
    """Convert DATABASE_URL to a synchronous psycopg2 DSN (for Alembic)."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
