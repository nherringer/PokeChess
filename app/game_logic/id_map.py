"""
Piece UUID tracking across apply_move() calls.

Piece.id is the canonical per-piece UUID carrier (set when state_from_dict()
loads a state from the DB).  apply_move() deep-copies the board via
dataclasses.replace(), so Piece.id survives undisturbed for unchanged pieces.
For pieces that are newly created by apply_move() (e.g. EVOLVE replaces the
king type), the new object starts with id=None.

remap_ids() handles both duties:
  1. Returns a fresh IdMap (position → UUID) for callers that still use it.
  2. Writes the resolved UUID directly onto each piece in new_state so that
     state_to_dict() can read piece.id without needing the map.
"""

from __future__ import annotations

from typing import Optional

from engine.state import GameState, Piece, PieceType, Team, PAWN_TYPES, SAFETYBALL_TYPES
from engine.moves import Move, ActionType

from .serialization import IdMap


def remap_ids(
    old_state: GameState,
    new_state: GameState,
    move: Move,
    old_id_map: IdMap,
) -> IdMap:
    """
    Produce an updated id_map after apply_move() has transformed old_state → new_state.

    The strategy: start from old_id_map. For each piece in new_state, determine which
    piece in old_state it corresponds to (by tracking known movements). Build a new
    id_map keyed by the piece's new position.

    Key transformations to handle:
    - Foresight resolution (piece killed at turn start, before the player's move)
    - The player's move itself (MOVE, ATTACK, QUICK_ATTACK, etc.)
    - Safetyball discharge (stored pieces auto-released when player uses another piece)
    - Safetyball store (ally absorbed on MOVE)
    - Pawn promotion (position may change, type changes)
    - Release (safetyball consumed, stored piece appears at same square)
    """
    new_map: IdMap = {}

    # Build a quick lookup of old positions → id
    # Include both regular and stored piece ids
    old_pos_ids: dict[tuple[int, int], Optional[str]] = {}
    old_stored_ids: dict[tuple[int, int], Optional[str]] = {}
    for key, val in old_id_map.items():
        if isinstance(key, tuple) and len(key) == 2 and isinstance(key[0], int):
            old_pos_ids[key] = val
        elif isinstance(key, tuple) and key[0] == "stored":
            old_stored_ids[key[1]] = val

    # For each piece in the new state, figure out where it came from
    for row in new_state.board:
        for piece in row:
            if piece is None:
                continue
            pos = (piece.row, piece.col)
            uid = _trace_piece_origin(
                piece, pos, old_state, new_state, move, old_pos_ids, old_stored_ids
            )
            if uid is not None:
                new_map[pos] = uid

            # Handle stored pieces inside safetyballs
            if piece.stored_piece is not None:
                stored_uid = _trace_stored_origin(
                    piece, old_state, old_pos_ids, old_stored_ids
                )
                if stored_uid is not None:
                    new_map[("stored", pos)] = stored_uid

    # Propagate resolved UUIDs directly to piece objects so piece.id stays
    # authoritative after this move.  Callers that already use the returned
    # IdMap are unaffected; future callers can rely on piece.id instead.
    for row_list in new_state.board:
        for piece in row_list:
            if piece is None:
                continue
            pos = (piece.row, piece.col)
            uid = new_map.get(pos)
            if uid is not None:
                piece.id = uid
            if piece.stored_piece is not None:
                stored_uid = new_map.get(("stored", pos))
                if stored_uid is not None:
                    piece.stored_piece.id = stored_uid

    return new_map


def _trace_piece_origin(
    piece: Piece,
    pos: tuple[int, int],
    old_state: GameState,
    new_state: GameState,
    move: Move,
    old_pos_ids: dict[tuple[int, int], Optional[str]],
    old_stored_ids: dict[tuple[int, int], Optional[str]],
) -> Optional[str]:
    """Determine the UUID of a piece in the new state by tracing where it came from."""

    # TRADE: pieces never swap squares — only items (and Eevee may evolve in place on target).
    if move.action_type == ActionType.TRADE:
        if pos == (move.piece_row, move.piece_col):
            uid = old_pos_ids.get(pos)
            if uid is not None:
                return uid
        if pos == (move.target_row, move.target_col):
            uid = old_pos_ids.get(pos)
            if uid is not None:
                return uid

    # EVOLVE: Pikachu/Eevee evolve in place (source square == destination).
    if move.action_type == ActionType.EVOLVE:
        src = (move.piece_row, move.piece_col)
        tgt = (move.target_row, move.target_col)
        if pos == src == tgt:
            uid = old_pos_ids.get(src)
            if uid is not None:
                return uid

    # Case 1: piece was at the same position in the old state and hasn't moved
    old_piece = old_state.piece_at(pos[0], pos[1])
    if old_piece is not None and _same_piece(old_piece, piece):
        return old_pos_ids.get(pos)

    # Case 2: piece moved here from the move's source position
    # (attack with KO, regular move, quick_attack secondary, etc.)
    old_source = old_state.piece_at(move.piece_row, move.piece_col)
    if old_source is not None and _same_team(old_source, piece):
        # The moved piece could be at target_row/target_col (move, attack-KO)
        # or at secondary_row/secondary_col (quick_attack)
        source_pos = (move.piece_row, move.piece_col)
        if source_pos in old_pos_ids:
            # Check if this piece is where the moved piece ended up
            if pos != source_pos:  # it actually moved
                # For QUICK_ATTACK: piece ends at secondary position
                if move.action_type == ActionType.QUICK_ATTACK:
                    if move.secondary_row is not None and pos == (move.secondary_row, move.secondary_col):
                        return old_pos_ids.get(source_pos)
                    if pos == (move.target_row, move.target_col):
                        # Eevee captured and moved to target, then moved again
                        return old_pos_ids.get(source_pos)
                # For other moves: piece ends at target position
                elif pos == (move.target_row, move.target_col):
                    return old_pos_ids.get(source_pos)

    # Case 3: piece was released from a safetyball (RELEASE action or auto-discharge)
    # A released piece appears at the safetyball's position
    # Check if there was a safetyball with a stored piece at this position
    if pos in old_stored_ids:
        return old_stored_ids.get(pos)

    # Case 4: piece was discharged from a safetyball that was elsewhere
    # (safetyball discharge happens when the player uses a non-safetyball piece)
    for (r, c), stored_id in old_stored_ids.items():
        old_sb = old_state.piece_at(r, c)
        if old_sb is not None and old_sb.stored_piece is not None:
            if _same_team(old_sb.stored_piece, piece) and (r, c) == pos:
                return stored_id

    # Case 5: piece was at a different position but didn't move via the player's move
    # This shouldn't happen in normal play, but as a fallback scan old positions.
    # Use piece.id as a tiebreaker when available to avoid swapping UUIDs between
    # duplicate-type pieces (e.g., two rooks or two knights on the same team).
    for old_pos, uid in old_pos_ids.items():
        old_p = old_state.piece_at(old_pos[0], old_pos[1])
        if old_p is not None and _same_piece(old_p, piece) and uid is not None:
            # When both pieces carry an id, they must match — otherwise this is
            # a different piece of the same type.
            if piece.id is not None and old_p.id is not None and piece.id != old_p.id:
                continue
            # Verify this piece isn't still at its old position in new_state
            new_at_old = new_state.piece_at(old_pos[0], old_pos[1])
            if new_at_old is None or not _same_piece(new_at_old, old_p):
                return uid

    return None


def _trace_stored_origin(
    carrier: Piece,
    old_state: GameState,
    old_pos_ids: dict[tuple[int, int], Optional[str]],
    old_stored_ids: dict[tuple[int, int], Optional[str]],
) -> Optional[str]:
    """Find the UUID of a piece that's now stored inside a safetyball."""
    if carrier.stored_piece is None:
        return None

    stored = carrier.stored_piece
    carrier_pos = (carrier.row, carrier.col)

    # Check if this safetyball already had a stored piece at its position
    if carrier_pos in old_stored_ids:
        return old_stored_ids[carrier_pos]

    # The stored piece was at the safetyball's current position before being absorbed
    # (safetyball moved onto an injured ally)
    target_id = old_pos_ids.get(carrier_pos)
    if target_id is not None:
        return target_id

    return None


def _same_piece(a: Piece, b: Piece) -> bool:
    """Heuristic: same team and same type (type may change on evolution/promotion)."""
    return a.team == b.team and a.piece_type == b.piece_type


def _same_team(a: Piece, b: Piece) -> bool:
    return a.team == b.team
