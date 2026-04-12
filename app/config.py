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
# A single "*" entry means “any origin”; main.py maps that to allow_origin_regex so
# credentialed requests work (browsers disallow Origin: * with credentials).
# Minutes a PvB player is considered "active" against a bot after their last move.
# The app divides the bot's base time_budget by the count of active players to
# share MCTS compute fairly under load.  See docs/load_aware_budgeting.md.
BOT_ACTIVE_WINDOW_MINUTES: int = int(os.environ.get("BOT_ACTIVE_WINDOW_MINUTES", "22"))

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

if len(SECRET_KEY) < 32 and ENVIRONMENT != "development":
    raise RuntimeError(
        f"SECRET_KEY is too short ({len(SECRET_KEY)} chars); minimum 32 required in non-development environments."
    )

_DATABASE_URL_DEFAULT = "postgresql+asyncpg://pokechess:pokechess@localhost:5432/pokechess"
if DATABASE_URL == _DATABASE_URL_DEFAULT and ENVIRONMENT != "development":
    raise RuntimeError(
        "DATABASE_URL is set to the default dev value in a non-development environment. "
        "Set DATABASE_URL to the production database connection string."
    )


def asyncpg_dsn() -> str:
    """Convert DATABASE_URL to a raw asyncpg-compatible DSN."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
