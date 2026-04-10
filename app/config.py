import os
import warnings

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://pokechess:pokechess@localhost:5432/pokechess"
)
ENGINE_URL: str = os.environ.get("ENGINE_URL", "http://localhost:5001")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
ALGORITHM: str = "HS256"
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "*").split(",")
    if o.strip()
]

if SECRET_KEY == "dev-secret-change-me-in-production" and ENVIRONMENT != "development":
    raise RuntimeError(
        "SECRET_KEY is set to the default dev value in a non-development environment. "
        "Set SECRET_KEY to a secure random string."
    )

if SECRET_KEY == "dev-secret-change-me-in-production":
    warnings.warn(
        "Using default SECRET_KEY — do not use in production",
        stacklevel=1,
    )


def asyncpg_dsn() -> str:
    """Convert DATABASE_URL to a raw asyncpg-compatible DSN."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def sync_dsn() -> str:
    """Convert DATABASE_URL to a synchronous psycopg2 DSN (for Alembic)."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
