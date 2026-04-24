"""
App-owned serialization for GameState ↔ JSONB.

The output JSON matches the games.state spec in pokechess_data_model.md exactly.

Piece.id is the canonical UUID carrier: after state_from_dict() every Piece has
its id set directly, and _piece_to_dict() reads it from there.  The id_map
parameter of state_to_dict() serves as a fallback for pieces that haven't been
through a round-trip yet (e.g. the freshly built GameState.new_game() before any
serialization), where ids come from the roster's IdMap built at game creation.
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
    HiddenItem,
    FloorItem,
    PIECE_STATS,
)

# Type alias for the piece-UUID map threaded through serialization and move handlers.
# Keys are either board positions (row, col) or stored-piece sentinels ("stored", (row, col)).
# Values are UUID strings for named pieces, or None for pawns / unnamed pieces.
IdMap = dict


# ---------------------------------------------------------------------------
# Serialization: GameState → dict
# ---------------------------------------------------------------------------

def _piece_to_dict(piece: Piece, id_map: IdMap) -> dict:
    # Prefer the id embedded on the piece itself (set by state_from_dict or remap_ids);
    # fall back to the id_map for pieces that haven't been through a round-trip yet.
    piece_id = piece.id if piece.id is not None else id_map.get((piece.row, piece.col))
    d = {
        "id": piece_id,
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
        "caster_row": fx.caster_row,
        "caster_col": fx.caster_col,
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
        "hidden_items": [
            {"row": h.row, "col": h.col, "item": h.item.name}
            for h in state.hidden_items
        ],
        "floor_items": [
            {"row": f.row, "col": f.col, "item": f.item.name}
            for f in state.floor_items
        ],
        "tall_grass_explored": [
            [r, c] for (r, c) in sorted(state.tall_grass_explored)
        ],
    }


# ---------------------------------------------------------------------------
# Player-masked view: state → dict with opponent secrets hidden
# ---------------------------------------------------------------------------

def _foresight_masked(fx: Optional[ForesightEffect]) -> Optional[dict]:
    """Foresight dict with target square hidden — sent to the non-casting player."""
    if fx is None:
        return None
    return {
        "target_row": -1,
        "target_col": -1,
        "damage": fx.damage,
        "resolves_on_turn": fx.resolves_on_turn,
        "caster_row": fx.caster_row,
        "caster_col": fx.caster_col,
    }


def player_view_of_state(state: GameState, team: Team, id_map: IdMap) -> dict:
    """
    Return a state dict masked for `team`'s perspective:
      - hidden_items omitted (bot/player cannot see unexplored grass contents)
      - Opponent pieces with held items have held_item replaced by "UNKNOWN"
      - floor_items and tall_grass_explored included in full
      - Opponent's pending_foresight has target_row/target_col stripped
    """
    board = []
    for row in state.board:
        for piece in row:
            if piece is None:
                continue
            d = _piece_to_dict(piece, id_map)
            if piece.team != team and piece.held_item.name != "NONE":
                d["held_item"] = "UNKNOWN"
            board.append(d)

    opponent = Team.BLUE if team == Team.RED else Team.RED

    pending_foresight = {}
    for t in (Team.RED, Team.BLUE):
        fx = state.pending_foresight[t]
        if t == opponent:
            pending_foresight[t.name] = _foresight_masked(fx)
        else:
            pending_foresight[t.name] = _foresight_to_dict(fx)

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
        "pending_foresight": pending_foresight,
        "board": board,
        "hidden_items": [],
        "floor_items": [
            {"row": f.row, "col": f.col, "item": f.item.name}
            for f in state.floor_items
        ],
        "tall_grass_explored": [
            [r, c] for (r, c) in sorted(state.tall_grass_explored)
        ],
    }


def mask_state_dict(state: dict, team_name: str) -> dict:
    """
    Mask a raw state dict for `team_name`'s perspective (applied to DB state dicts).
    Hides opponent held items, clears hidden_items, and strips foresight target from opponent.
    """
    import copy
    masked = copy.deepcopy(state)
    for piece in masked.get("board", []):
        if piece.get("team") != team_name and piece.get("held_item", "NONE") not in ("NONE", "UNKNOWN"):
            piece["held_item"] = "UNKNOWN"
    masked["hidden_items"] = []
    opponent = "BLUE" if team_name == "RED" else "RED"
    opp_fx = masked.get("pending_foresight", {}).get(opponent)
    if opp_fx is not None:
        opp_fx.pop("target_row", None)
        opp_fx.pop("target_col", None)
    return masked


def mask_history_foresight(history: list[dict], team_name: str) -> list[dict]:
    """
    Strip foresight target coordinates from history entries cast by the opponent team.
    Called at serve time so the requesting player can't learn where foresight is aimed.
    """
    import copy
    result = []
    for entry in history:
        if entry.get("action_type") == "foresight" and entry.get("player") != team_name:
            entry = copy.copy(entry)
            entry.pop("to_row", None)
            entry.pop("to_col", None)
            if isinstance(entry.get("result"), dict):
                r = copy.copy(entry["result"])
                r.pop("target_row", None)
                r.pop("target_col", None)
                entry = {**entry, "result": r}
        result.append(entry)
    return result


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
    # Propagate the id directly onto the Piece so it survives copy() and
    # apply_move() without needing the parallel id_map on every read.
    piece.id = d.get("id")
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
        caster_row=d.get("caster_row", -1),
        caster_col=d.get("caster_col", -1),
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
        hidden_items=[
            HiddenItem(row=h["row"], col=h["col"], item=Item[h["item"]])
            for h in data.get("hidden_items", [])
        ],
        floor_items=[
            FloorItem(row=f["row"], col=f["col"], item=Item[f["item"]])
            for f in data.get("floor_items", [])
        ],
        tall_grass_explored={
            (sq[0], sq[1]) for sq in data.get("tall_grass_explored", [])
        },
    )
    return state, id_map
