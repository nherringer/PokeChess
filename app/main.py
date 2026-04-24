import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .db.connection import create_pool, close_pool

limiter = Limiter(key_func=get_remote_address)


class AppError(Exception):
    def __init__(self, status_code: int, error: str, detail: str):
        self.status_code = status_code
        self.error = error
        self.detail = detail


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Route INFO-level messages from our own loggers (e.g. app.routes.moves) to
    # stderr. Without this, logger.info calls are silently dropped because
    # no handler is attached to the root logger — uvicorn configures its own
    # loggers but not ours. Called here (not at module level) so it only fires
    # on server start, not on import.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.state.db_pool = await create_pool()
    app.state.engine_client = httpx.AsyncClient(
        base_url=app.state.engine_url, timeout=15.0
    )
    yield
    await app.state.engine_client.aclose()
    await close_pool()


def create_app() -> FastAPI:
    from . import config
    from .routes import auth, users, friends, invites, games, moves, bots

    docs_url = "/docs" if config.ENVIRONMENT == "development" else None
    redoc_url = "/redoc" if config.ENVIRONMENT == "development" else None
    openapi_url = "/openapi.json" if config.ENVIRONMENT == "development" else None
    app = FastAPI(
        title="PokeChess",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    # TRUSTED_PROXY_IPS must be the ALB/VPC CIDR in production so that get_remote_address
    # resolves to the true client IP rather than a spoofed X-Forwarded-For value.
    # Leaving it as "*" in production would let attackers rotate XFF per request and
    # bypass per-IP rate limits entirely. config.py documents the required value.
    if config.ENVIRONMENT != "development" and config.TRUSTED_PROXY_IPS == "*":
        raise RuntimeError(
            "TRUSTED_PROXY_IPS cannot be '*' in non-development environments. "
            "Set it to the ALB/VPC CIDR (e.g. '10.0.0.0/16') so that rate limits "
            "cannot be bypassed via X-Forwarded-For spoofing."
        )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=config.TRUSTED_PROXY_IPS)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.state.engine_url = config.ENGINE_URL

    # Browsers reject Access-Control-Allow-Origin: * together with credentialed requests.
    # When CORS_ORIGINS is "*", mirror the request Origin via regex instead.
    cors_origins = config.CORS_ORIGINS
    if config.ENVIRONMENT != "development" and cors_origins == ["*"]:
        raise RuntimeError(
            "CORS_ORIGINS cannot be '*' in non-development environments. "
            "Set CORS_ORIGINS to an explicit comma-separated allowlist."
        )
    if cors_origins == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r".*",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "detail": exc.detail},
        )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(friends.router)
    app.include_router(invites.router)
    app.include_router(games.router)
    app.include_router(moves.router)
    app.include_router(bots.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
