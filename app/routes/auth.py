from __future__ import annotations

from fastapi import APIRouter, Request, Response
from asyncpg import UniqueViolationError

from .. import config
from ..auth import (
    Db,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    uuid_from_jwt_sub,
)
from ..main import AppError
from ..schemas import RegisterRequest, LoginRequest, TokenResponse, RefreshResponse
from ..db.queries import users as user_q, settings as settings_q

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(body: RegisterRequest, response: Response, db: Db):
    pw_hash = hash_password(body.password)
    try:
        user = await user_q.insert_user(db, body.username, body.email, pw_hash)
    except UniqueViolationError:
        raise AppError(409, "conflict", "Username or email already exists")

    await settings_q.create_default_settings(db, user["id"])

    access = create_access_token(user["id"])
    refresh = create_refresh_token(user["id"])
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=config.ENVIRONMENT != "development",
        samesite="lax",
        path="/auth/refresh",
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    return TokenResponse(access_token=access, user_id=user["id"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: Db):
    user = await user_q.get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise AppError(401, "unauthorized", "Invalid email or password")

    access = create_access_token(user["id"])
    refresh = create_refresh_token(user["id"])
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=config.ENVIRONMENT != "development",
        samesite="lax",
        path="/auth/refresh",
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    return TokenResponse(access_token=access, user_id=user["id"])


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db: Db):
    token = request.cookies.get("refresh_token")
    if token is None:
        raise AppError(401, "unauthorized", "No refresh token cookie")
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AppError(401, "unauthorized", "Invalid refresh token")
    user_id = payload.get("sub")
    if user_id is None:
        raise AppError(401, "unauthorized", "Invalid token payload")
    row = await db.fetchrow("SELECT id FROM users WHERE id = $1", uuid_from_jwt_sub(str(user_id)))
    if row is None:
        raise AppError(401, "unauthorized", "User not found")
    access = create_access_token(row["id"])
    return RefreshResponse(access_token=access)
