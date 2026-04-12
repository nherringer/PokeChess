from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from asyncpg import UniqueViolationError

from ..auth import Db, CurrentUser
from ..main import AppError
from ..schemas import (
    FriendsResponse,
    SendFriendRequest,
    FriendActionRequest,
    FriendActionResponse,
)
from ..db.queries import friends as friend_q, users as user_q

router = APIRouter(prefix="/friends", tags=["friends"])


@router.get("", response_model=FriendsResponse)
async def list_friends(user: CurrentUser, db: Db):
    data = await friend_q.get_friends_and_requests(db, user["id"])
    return FriendsResponse(**data)


@router.post("", status_code=201, response_model=FriendActionResponse)
async def send_friend_request(body: SendFriendRequest, user: CurrentUser, db: Db):
    if body.username:
        target = await user_q.get_user_by_username(db, body.username)
    elif body.email:
        target = await user_q.get_user_by_email_public(db, body.email)
    else:
        raise AppError(400, "bad_request", "Provide either 'username' or 'email'")
    if target is None:
        raise AppError(404, "not_found", "User not found")
    if target["id"] == user["id"]:
        raise AppError(400, "bad_request", "Cannot send a friend request to yourself")
    try:
        result = await friend_q.insert_friendship(db, user["id"], target["id"], user["id"])
    except UniqueViolationError:
        raise AppError(409, "conflict", "Friend request already exists")
    return FriendActionResponse(**result)


@router.put("/{friendship_id}", response_model=FriendActionResponse)
async def respond_to_friend_request(
    friendship_id: UUID, body: FriendActionRequest, user: CurrentUser, db: Db
):
    if body.action not in ("accept", "reject"):
        raise AppError(400, "bad_request", "Action must be 'accept' or 'reject'")
    fs = await friend_q.get_friendship(db, friendship_id)
    if fs is None:
        raise AppError(404, "not_found", "Friendship not found")
    if fs["status"] != "pending":
        raise AppError(400, "bad_request", "Request is not pending")
    # Only the non-initiator can accept/reject
    if fs["initiator_id"] == user["id"]:
        raise AppError(403, "forbidden", "Cannot respond to your own friend request")
    # Verify current user is actually part of this friendship
    if user["id"] not in (fs["user_a_id"], fs["user_b_id"]):
        raise AppError(403, "forbidden", "Not your friend request")

    new_status = "accepted" if body.action == "accept" else "rejected"
    result = await friend_q.update_friendship_status(db, friendship_id, new_status)
    if result is None:
        raise AppError(404, "not_found", "Friendship not found")
    return FriendActionResponse(**result)
