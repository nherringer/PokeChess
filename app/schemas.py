from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Limits merged JSON patch size for user_settings.extra_settings (abuse / accidental huge payloads).
_MAX_EXTRA_SETTINGS_BYTES = 16_384
_MAX_EXTRA_SETTINGS_DEPTH = 8


def _extra_settings_depth(obj: object, depth: int) -> None:
    if depth > _MAX_EXTRA_SETTINGS_DEPTH:
        raise ValueError(
            f"extra_settings must not nest deeper than {_MAX_EXTRA_SETTINGS_DEPTH} levels"
        )
    if isinstance(obj, dict):
        for v in obj.values():
            _extra_settings_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _extra_settings_depth(v, depth + 1)


def _validate_extra_settings_dict(value: dict) -> dict:
    try:
        raw = json.dumps(value)
    except (TypeError, ValueError) as e:
        raise ValueError("extra_settings must be JSON-serializable") from e
    if len(raw) > _MAX_EXTRA_SETTINGS_BYTES:
        raise ValueError(
            f"extra_settings must be at most {_MAX_EXTRA_SETTINGS_BYTES} bytes when serialized"
        )
    _extra_settings_depth(value, 0)
    return value


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=8)
    access_code: str | None = None  # TEMP: registration gate — remove field for public launch


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
    set_side: str
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

    @field_validator("extra_settings")
    @classmethod
    def _limit_extra_settings(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        return _validate_extra_settings_dict(v)


class SettingsOut(BaseModel):
    board_theme: str
    extra_settings: dict
    updated_at: datetime | None


class StarterResponse(BaseModel):
    pieces: list[PieceOut]


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
    username: str | None = None
    email: str | None = None

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "SendFriendRequest":
        if not self.username and not self.email:
            raise ValueError("Provide either 'username' or 'email'")
        if self.username and self.email:
            raise ValueError("Provide either 'username' or 'email', not both")
        return self


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
    player_side: str  # "red" | "blue" | "random"

    @field_validator("player_side")
    @classmethod
    def _valid_player_side(cls, v: str) -> str:
        if v not in ("red", "blue", "random"):
            raise ValueError("player_side must be 'red', 'blue', or 'random'")
        return v


class InviteOut(BaseModel):
    """Pending PvP invite for the current user (incoming or outgoing)."""

    id: UUID
    game_id: UUID
    created_at: datetime
    direction: str  # "incoming" | "outgoing"
    other_user_id: UUID
    other_username: str
    inviter_id: UUID
    invitee_id: UUID
    inviter_side: str  # "red" | "blue" — always concrete (random resolved at creation)


class InviteActionRequest(BaseModel):
    action: str  # "accept" or "reject"


class InviteActionResponse(BaseModel):
    invite_id: UUID
    status: str
    game_id: UUID


# ---------------------------------------------------------------------------
# Bots
# ---------------------------------------------------------------------------

class BotOut(BaseModel):
    id: UUID
    name: str
    stars: int
    flavor: str
    forced_player_side: str | None  # "red" | "blue" | None
    accent_color: str               # CSS hex string, e.g. "#be2d2d"
    trainer_sprite: str             # filename, e.g. "teamrocket.png"
    time_budget: float | None = None


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
    # Populated by GET /games list query (joined users / bots)
    opponent_display: str | None = None
    my_side: str | None = None  # "red" | "blue" — requesting user's team


class GameDetail(BaseModel):
    id: UUID
    status: str
    whose_turn: str | None
    turn_number: int
    is_bot_game: bool
    bot_side: str | None
    bot_name: str | None = None
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
