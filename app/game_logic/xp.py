"""
XP attribution from move history.

v1 formula: XP earned = total damage dealt by that piece during the game.
Each attack move with a `damage` field in its result contributes.
Pokeball captures (no damage) do not contribute.
Foresight_resolve entries also have a `damage` field.
"""

from __future__ import annotations


def compute_xp(move_history: list[dict]) -> dict[str, int]:
    """
    Compute per-piece XP from a complete move_history array.

    Returns: dict mapping piece_id (str UUID) → total XP earned.
    Pieces with id=None (pawns) are excluded.
    """
    xp: dict[str, int] = {}
    for entry in move_history:
        piece_id = entry.get("piece_id")
        if piece_id is None:
            continue
        result = entry.get("result", {})
        damage = result.get("damage")
        if damage is not None and damage > 0:
            xp[piece_id] = xp.get(piece_id, 0) + damage
    return xp
