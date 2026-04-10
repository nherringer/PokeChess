"""
App-owned serialization for GameState ↔ JSONB.

This exists because the engine's Piece.id and GameState.to_dict()/from_dict()
are not yet implemented (ML-engineer blockers #1 and #2 in the roadmap).
The output JSON matches the games.state spec in pokechess_data_model.md exactly.

When the engine adds these methods, this module can delegate to them or be removed.
"""

from __future__ import annotations

from typing import Optional

from engine.state import (
    GameState,
    Piece,
    PieceType,
    Team,
    Item,
    ForesightEffect,
    PIECE_STATS,
)

# Type alias: board position → piece UUID (None for pawns / unnamed pieces)
IdMap = dict[tuple[int, int], Optional[str]]


# ---------------------------------------------------------------------------
# Serialization: GameState → dict
# ---------------------------------------------------------------------------

def _piece_to_dict(piece: Piece, id_map: IdMap) -> dict:
    d = {
        "id": id_map.get((piece.row, piece.col)),
        "piece_type": piece.piece_type.name,
        "team": piece.team.name,
        "row": piece.row,
        "col": piece.col,
        "current_hp": piece.current_hp,
        "held_item": piece.held_item.name,
        "stored_piece": None,
    }
    if piece.stored_piece is not None:
        d["stored_piece"] = _piece_to_dict(piece.stored_piece, id_map)
    return d


def _foresight_to_dict(fx: Optional[ForesightEffect]) -> Optional[dict]:
    if fx is None:
        return None
    return {
        "target_row": fx.target_row,
        "target_col": fx.target_col,
        "damage": fx.damage,
        "resolves_on_turn": fx.resolves_on_turn,
    }


def state_to_dict(state: GameState, id_map: IdMap) -> dict:
    board = []
    for row in state.board:
        for piece in row:
            if piece is not None:
                board.append(_piece_to_dict(piece, id_map))
    return {
        "active_player": state.active_player.name,
        "turn_number": state.turn_number,
        "has_traded": {
            "RED": state.has_traded[Team.RED],
            "BLUE": state.has_traded[Team.BLUE],
        },
        "foresight_used_last_turn": {
            "RED": state.foresight_used_last_turn[Team.RED],
            "BLUE": state.foresight_used_last_turn[Team.BLUE],
        },
        "pending_foresight": {
            "RED": _foresight_to_dict(state.pending_foresight[Team.RED]),
            "BLUE": _foresight_to_dict(state.pending_foresight[Team.BLUE]),
        },
        "board": board,
    }


# ---------------------------------------------------------------------------
# Deserialization: dict → GameState + IdMap
# ---------------------------------------------------------------------------

def _piece_from_dict(d: dict) -> Piece:
    piece = Piece(
        piece_type=PieceType[d["piece_type"]],
        team=Team[d["team"]],
        row=d["row"],
        col=d["col"],
        current_hp=d["current_hp"],
        held_item=Item[d["held_item"]],
    )
    if d.get("stored_piece") is not None:
        piece.stored_piece = _piece_from_dict(d["stored_piece"])
    return piece


def _foresight_from_dict(d: Optional[dict]) -> Optional[ForesightEffect]:
    if d is None:
        return None
    return ForesightEffect(
        target_row=d["target_row"],
        target_col=d["target_col"],
        damage=d["damage"],
        resolves_on_turn=d["resolves_on_turn"],
    )


def state_from_dict(data: dict) -> tuple[GameState, IdMap]:
    """Reconstruct a GameState and extract the piece-UUID id_map."""
    board: list[list[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
    id_map: IdMap = {}

    for pd in data["board"]:
        piece = _piece_from_dict(pd)
        board[piece.row][piece.col] = piece
        piece_id = pd.get("id")
        if piece_id is not None:
            id_map[(piece.row, piece.col)] = piece_id
        # Also track stored piece IDs (safetyball passengers)
        if pd.get("stored_piece") and pd["stored_piece"].get("id"):
            # Stored pieces share the safetyball's position in id_map keying.
            # We store them under a special key to avoid collisions.
            stored_pos = (piece.row, piece.col)
            id_map[("stored", stored_pos)] = pd["stored_piece"]["id"]

    state = GameState(
        board=board,
        active_player=Team[data["active_player"]],
        turn_number=data["turn_number"],
        pending_foresight={
            Team.RED: _foresight_from_dict(data["pending_foresight"]["RED"]),
            Team.BLUE: _foresight_from_dict(data["pending_foresight"]["BLUE"]),
        },
        foresight_used_last_turn={
            Team.RED: data["foresight_used_last_turn"]["RED"],
            Team.BLUE: data["foresight_used_last_turn"]["BLUE"],
        },
        has_traded={
            Team.RED: data["has_traded"]["RED"],
            Team.BLUE: data["has_traded"]["BLUE"],
        },
    )
    return state, id_map
