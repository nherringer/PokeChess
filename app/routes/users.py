from __future__ import annotations

from fastapi import APIRouter

from ..auth import Db, CurrentUser
from ..main import AppError
from ..schemas import UserProfile, PieceOut, SettingsUpdate, SettingsOut
from ..db.queries import users as user_q, settings as settings_q

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_me(user: CurrentUser, db: Db):
    pieces = await user_q.get_user_pieces(db, user["id"])
    return UserProfile(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        created_at=user["created_at"],
        pieces=[PieceOut(**p) for p in pieces],
    )


@router.patch("/me/settings", response_model=SettingsOut)
async def update_my_settings(body: SettingsUpdate, user: CurrentUser, db: Db):
    result = await settings_q.update_settings(
        db, user["id"], body.board_theme, body.extra_settings
    )
    if result is None:
        raise AppError(404, "not_found", "Settings not found")
    return SettingsOut(**result)
