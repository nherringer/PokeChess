from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db.connection import create_pool, close_pool


class AppError(Exception):
    def __init__(self, status_code: int, error: str, detail: str):
        self.status_code = status_code
        self.error = error
        self.detail = detail


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    app.state.engine_client = httpx.AsyncClient(
        base_url=app.state.engine_url, timeout=15.0
    )
    yield
    await app.state.engine_client.aclose()
    await close_pool()


def create_app() -> FastAPI:
    from . import config
    from .routes import auth, users, friends, invites, games, moves

    app = FastAPI(title="PokeChess", lifespan=lifespan)
    app.state.engine_url = config.ENGINE_URL

    # Browsers reject Access-Control-Allow-Origin: * together with credentialed requests.
    # When CORS_ORIGINS is "*", mirror the request Origin via regex instead.
    cors_origins = config.CORS_ORIGINS
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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
