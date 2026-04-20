import os

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
ENGINE_URL: str = os.environ.get("ENGINE_URL", "http://localhost:5001")
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
BOT_API_SECRET: str = os.environ.get("BOT_API_SECRET", "")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
ALGORITHM: str = "HS256"
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "production")
# Restrict to the ALB/VPC CIDR in production (e.g. "10.0.0.0/16") so the rate
# limiter cannot be bypassed by spoofing X-Forwarded-For headers through the ALB.
# main.py raises RuntimeError if this is "*" outside development.
TRUSTED_PROXY_IPS: str = os.environ.get("TRUSTED_PROXY_IPS", "*")
# A single "*" entry means "any origin"; main.py maps that to allow_origin_regex so
# credentialed requests work (browsers disallow Origin: * with credentials).
# Minutes a PvB player is considered "active" against a bot after their last move.
# The app divides the bot's base time_budget by the count of active players to
# share MCTS compute fairly under load.  See docs/load_aware_budgeting.md.
BOT_ACTIVE_WINDOW_MINUTES: int = int(os.environ.get("BOT_ACTIVE_WINDOW_MINUTES", "22"))
# TEMP: registration gate — remove for public launch
REGISTRATION_ACCESS_CODE: str = os.environ.get("REGISTRATION_ACCESS_CODE", "")
# END TEMP

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "").split(",")
    if o.strip()
]

if not CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS is not set. "
        "Set it via environment variable or .env file (e.g. 'https://yourdomain.com' or '*' for local dev)."
    )

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. "
        "Set it via environment variable or .env file (minimum 32 characters)."
    )

if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError(
        f"JWT_SECRET_KEY is too short ({len(JWT_SECRET_KEY)} chars); minimum 32 required."
    )

if not BOT_API_SECRET:
    raise RuntimeError(
        "BOT_API_SECRET is not set. "
        "Set it via environment variable or .env file (minimum 32 characters)."
    )

if len(BOT_API_SECRET) < 32:
    raise RuntimeError(
        f"BOT_API_SECRET is too short ({len(BOT_API_SECRET)} chars); minimum 32 required."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Set it via environment variable or .env file."
    )


def asyncpg_dsn() -> str:
    """Convert DATABASE_URL to a raw asyncpg-compatible DSN."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
