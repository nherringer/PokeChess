"""
Encode a Python GameState into the binary wire format consumed by the C++ engine.

Wire layout (little-endian):
  Header   7 bytes: active_player(B) turn(H) traded_red(B) traded_blue(B)
                    fs_used_red(B) fs_used_blue(B)
  Foresight RED  7 bytes: active(B) row(B) col(B) damage(h) resolves(H)
  Foresight BLUE 7 bytes: same
  n_pieces  1 byte
  Per piece 14 bytes: type(B) team(B) row(B) col(B) hp(h) item(B)
                      has_stored(B) stored_type(B) stored_team(B) stored_hp(h)
                      stored_item(B) _pad(x)
"""
from __future__ import annotations
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.state import GameState

_HEADER_FMT  = '<BHBBBB'          # 7 bytes
_FORESIGHT_FMT = '<BBBhH'         # 7 bytes
_PIECE_FMT   = '<BBBBhBBBBhBx'   # 14 bytes

# Pre-compiled struct objects for speed
_HDR  = struct.Struct(_HEADER_FMT)
_FS   = struct.Struct(_FORESIGHT_FMT)
_PC   = struct.Struct(_PIECE_FMT)


def encode_state(state: 'GameState') -> bytes:
    """Return the binary wire encoding of *state* for the C++ engine."""
    from engine.state import Team, PieceType

    active = 1 if state.active_player == Team.RED else 2

    # Header
    buf = _HDR.pack(
        active,
        state.turn_number,
        1 if state.has_traded[Team.RED]  else 0,
        1 if state.has_traded[Team.BLUE] else 0,
        1 if state.foresight_used_last_turn[Team.RED]  else 0,
        1 if state.foresight_used_last_turn[Team.BLUE] else 0,
    )

    # Foresight for RED then BLUE
    for team in (Team.RED, Team.BLUE):
        fx = state.pending_foresight[team]
        if fx is not None:
            buf += _FS.pack(1, fx.target_row, fx.target_col,
                            fx.damage, fx.resolves_on_turn)
        else:
            buf += _FS.pack(0, 0, 0, 0, 0)

    # Collect all on-board pieces (stored pieces are encoded inside their carrier)
    pieces = [p for row in state.board for p in row if p is not None]
    buf += struct.pack('<B', len(pieces))

    for p in pieces:
        team_byte  = 1 if p.team == Team.RED else 2
        ptype_byte = p.piece_type.value
        item_byte  = p.held_item.value

        has_stored = 0
        st_type = st_team = st_hp = st_item = 0
        if p.stored_piece is not None:
            has_stored = 1
            st = p.stored_piece
            st_type = st.piece_type.value
            st_team = 1 if st.team == Team.RED else 2
            st_hp   = st.current_hp
            st_item = st.held_item.value

        buf += _PC.pack(
            ptype_byte, team_byte, p.row, p.col, p.current_hp, item_byte,
            has_stored, st_type, st_team, st_hp, st_item,
        )

    return buf
