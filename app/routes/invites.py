from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from asyncpg import UniqueViolationError

from ..auth import Db, CurrentUser
from ..main import AppError
from ..schemas import SendInviteRequest, InviteOut, InviteActionRequest, InviteActionResponse
from ..db.queries import invites as invite_q, friends as friend_q

router = APIRouter(prefix="/game-invites", tags=["invites"])


@router.get("", response_model=list[InviteOut])
async def list_invites(user: CurrentUser, db: Db):
    rows = await invite_q.get_pending_invites(db, user["id"])
    return [InviteOut(**r) for r in rows]


@router.post("", status_code=201, response_model=InviteActionResponse)
async def send_invite(body: SendInviteRequest, user: CurrentUser, db: Db):
    # Must be friends
    if not await friend_q.are_friends(db, user["id"], body.invitee_id):
        raise AppError(404, "not_found", "Invitee is not a friend")
    if await invite_q.has_pending_invite_between(db, user["id"], body.invitee_id):
        raise AppError(
            409,
            "conflict",
            "A pending game invite already exists with this player",
        )
    try:
        result = await invite_q.insert_invite_and_game(
            db, user["id"], body.invitee_id, body.player_side
        )
    except UniqueViolationError:
        raise AppError(409, "conflict", "An active game already exists between these players")
    return InviteActionResponse(**result)


@router.delete("/{invite_id}", response_model=InviteActionResponse)
async def cancel_invite(invite_id: UUID, user: CurrentUser, db: Db):
    """Withdraw a pending invite (inviter only)."""
    inv = await invite_q.get_invite(db, invite_id)
    if inv is None:
        raise AppError(404, "not_found", "Invite not found")
    if inv["inviter_id"] != user["id"]:
        raise AppError(403, "forbidden", "Only the inviter can cancel this invite")
    if inv["status"] != "pending":
        raise AppError(400, "bad_request", "Invite is not pending")
    await invite_q.update_invite_status(db, invite_id, "rejected")
    return InviteActionResponse(
        invite_id=inv["id"], status="rejected", game_id=inv["game_id"]
    )


@router.put("/{invite_id}", response_model=InviteActionResponse)
async def respond_to_invite(
    invite_id: UUID, body: InviteActionRequest, user: CurrentUser, db: Db
):
    if body.action not in ("accept", "reject"):
        raise AppError(400, "bad_request", "Action must be 'accept' or 'reject'")
    inv = await invite_q.get_invite(db, invite_id)
    if inv is None:
        raise AppError(404, "not_found", "Invite not found")
    if inv["invitee_id"] != user["id"]:
        raise AppError(403, "forbidden", "Only the invitee can respond")
    if inv["status"] != "pending":
        raise AppError(400, "bad_request", "Invite is not pending")

    if body.action == "reject":
        await invite_q.update_invite_status(db, invite_id, "rejected")
        return InviteActionResponse(
            invite_id=inv["id"], status="rejected", game_id=inv["game_id"]
        )

    # Accept: update invite + initialize game in one transaction.
    # red_player_id / blue_player_id were set correctly when the invite was created
    # (inviter_side resolved, sides assigned at that point), so we read them from the
    # game row rather than re-deriving from inviter/invitee ordering.
    from ..game_logic.roster import initialize_pvp_game

    async with db.transaction():
        await invite_q.update_invite_status(db, invite_id, "accepted")
        await initialize_pvp_game(
            db,
            inv["game_id"],
            red_player_id=inv["red_player_id"],
            blue_player_id=inv["blue_player_id"],
        )

    return InviteActionResponse(
        invite_id=inv["id"], status="accepted", game_id=inv["game_id"]
    )
