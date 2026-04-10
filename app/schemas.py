from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Users / Settings
# ---------------------------------------------------------------------------

class PieceOut(BaseModel):
    id: UUID
    role: str
    species: str
    xp: int
    evolution_stage: int


class UserProfile(BaseModel):
    id: UUID
    username: str
    email: str
    created_at: datetime
    pieces: list[PieceOut]


class SettingsUpdate(BaseModel):
    board_theme: str | None = None
    extra_settings: dict | None = None


class SettingsOut(BaseModel):
    board_theme: str
    extra_settings: dict
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

class FriendUser(BaseModel):
    user_id: UUID
    username: str


class FriendRequest(BaseModel):
    id: UUID
    from_user_id: UUID | None = None
    to_user_id: UUID | None = None
    username: str


class FriendsResponse(BaseModel):
    friends: list[FriendUser]
    incoming: list[FriendRequest]
    outgoing: list[FriendRequest]


class SendFriendRequest(BaseModel):
    username: str


class FriendActionRequest(BaseModel):
    action: str  # "accept" or "reject"


class FriendActionResponse(BaseModel):
    id: UUID
    status: str


# ---------------------------------------------------------------------------
# Game Invites
# ---------------------------------------------------------------------------

class SendInviteRequest(BaseModel):
    invitee_id: UUID


class InviteOut(BaseModel):
    id: UUID
    from_user_id: UUID
    from_username: str
    game_id: UUID
    created_at: datetime


class InviteActionRequest(BaseModel):
    action: str  # "accept" or "reject"


class InviteActionResponse(BaseModel):
    invite_id: UUID
    status: str
    game_id: UUID


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

class CreateGameRequest(BaseModel):
    bot_id: UUID
    player_side: str  # "red" or "blue"


class GameSummary(BaseModel):
    id: UUID
    status: str
    whose_turn: str | None
    turn_number: int
    is_bot_game: bool
    bot_side: str | None
    red_player_id: UUID | None
    blue_player_id: UUID | None
    winner: str | None
    updated_at: datetime


class GameDetail(BaseModel):
    id: UUID
    status: str
    whose_turn: str | None
    turn_number: int
    is_bot_game: bool
    bot_side: str | None
    red_player_id: UUID | None
    blue_player_id: UUID | None
    winner: str | None
    end_reason: str | None
    state: dict | None
    move_history: list[dict]


class GamesListResponse(BaseModel):
    active: list[GameSummary]
    completed: list[GameSummary]


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------

class MovePayload(BaseModel):
    piece_row: int
    piece_col: int
    action_type: str
    target_row: int
    target_col: int
    secondary_row: int | None = None
    secondary_col: int | None = None
    move_slot: int | None = None


class LegalMoveOut(BaseModel):
    piece_row: int
    piece_col: int
    action_type: str
    target_row: int
    target_col: int
    secondary_row: int | None
    secondary_col: int | None
    move_slot: int | None
