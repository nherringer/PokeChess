"""
Build move_history entries from old vs new game state diffs.

Each engine ActionType + piece context maps to one of 10 history action_type
strings. The builder produces the exact JSON shapes defined in
docs/pokechess_data_model.md § games.move_history.
"""

from __future__ import annotations

from typing import Optional

from engine.state import (
    GameState,
    Piece,
    PieceType,
    Team,
    MATCHUP,
    PIECE_STATS,
    PAWN_TYPES,
    SAFETYBALL_TYPES,
    ForesightEffect,
)
from engine.moves import Move, ActionType

from .serialization import IdMap


# ---------------------------------------------------------------------------
# Damage calculation (mirrors engine/rules.py _calc_damage)
# ---------------------------------------------------------------------------

_BASE_DAMAGE: dict[PieceType, int] = {
    PieceType.SQUIRTLE: 100,
    PieceType.CHARMANDER: 100,
    PieceType.BULBASAUR: 100,
    PieceType.PIKACHU: 100,
    PieceType.RAICHU: 100,
    PieceType.EEVEE: 50,
    PieceType.VAPOREON: 100,
    PieceType.FLAREON: 100,
    PieceType.LEAFEON: 100,
    PieceType.JOLTEON: 100,
    PieceType.ESPEON: 80,
}

from engine.state import PokemonType

_MEW_SLOT_TYPES: dict[int, PokemonType] = {
    0: PokemonType.FIRE,
    1: PokemonType.WATER,
    2: PokemonType.GRASS,
}

_FORESIGHT_DAMAGE: dict[PieceType, int] = {
    PieceType.MEW: 120,
    PieceType.ESPEON: 120,
}


def _calc_damage(attacker: Piece, target: Piece, move_slot: Optional[int] = None) -> tuple[int, float]:
    """Return (damage, type_multiplier)."""
    if attacker.piece_type == PieceType.MEW:
        base = 100
        atk_type = _MEW_SLOT_TYPES.get(move_slot, PokemonType.FIRE)
    else:
        base = _BASE_DAMAGE.get(attacker.piece_type, 60)
        atk_type = attacker.pokemon_type

    type_mult = MATCHUP[atk_type][target.pokemon_type]
    raw = base * type_mult
    damage = max(10, int(round(raw / 10)) * 10)
    return damage, type_mult


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_history_entry(
    old_state: GameState,
    new_state: GameState,
    move: Move,
    id_map: IdMap,
    rng_roll: Optional[float] = None,
    captured: Optional[bool] = None,
) -> dict:
    """
    Build a single move_history entry for the player's chosen move.

    rng_roll / captured are provided for pokeball attacks where the app
    chose a specific outcome branch.
    """
    piece = old_state.board[move.piece_row][move.piece_col]
    piece_id = id_map.get((move.piece_row, move.piece_col))
    player = old_state.active_player.name
    turn = old_state.turn_number

    at = move.action_type

    if at == ActionType.MOVE:
        return _build_move(old_state, piece, move, piece_id, player, turn, id_map)
    elif at == ActionType.ATTACK:
        if piece.piece_type == PieceType.POKEBALL:
            return _build_pokeball_attack(
                old_state, piece, move, piece_id, player, turn, id_map, rng_roll, captured
            )
        elif piece.piece_type == PieceType.MASTERBALL:
            return _build_masterball_attack(
                old_state, piece, move, piece_id, player, turn, id_map
            )
        else:
            return _build_attack(old_state, piece, move, piece_id, player, turn, id_map)
    elif at == ActionType.QUICK_ATTACK:
        return _build_quick_attack(old_state, piece, move, piece_id, player, turn, id_map)
    elif at == ActionType.FORESIGHT:
        return _build_foresight(old_state, piece, move, piece_id, player, turn)
    elif at == ActionType.EVOLVE:
        return _build_evolve(old_state, new_state, piece, move, piece_id, player, turn)
    elif at == ActionType.TRADE:
        return _build_trade(old_state, new_state, piece, move, piece_id, player, turn, id_map)
    elif at == ActionType.RELEASE:
        return _build_release(old_state, piece, move, piece_id, player, turn, id_map)
    else:
        return {
            "turn": turn,
            "player": player,
            "action_type": at.name.lower(),
            "piece_id": piece_id,
            "result": {},
        }


def build_foresight_resolve_entry(
    old_state: GameState,
    new_state: GameState,
    fx: ForesightEffect,
    id_map: IdMap,
) -> Optional[dict]:
    """
    Build a foresight_resolve history entry if foresight resolved this turn.

    Call BEFORE the player's move is applied (since apply_move resolves foresight
    internally, compare old_state's pending vs new_state's pending to detect it).
    """
    player = old_state.active_player

    # Find the foresight caster's piece_id
    # The caster is on the same team as pending_foresight[player]
    caster_id = None
    for pos, uid in id_map.items():
        if isinstance(pos, tuple) and len(pos) == 2 and isinstance(pos[0], int):
            p = old_state.board[pos[0]][pos[1]]
            if p is not None and p.team == player and p.piece_type in (PieceType.MEW, PieceType.ESPEON):
                caster_id = uid
                break

    target = old_state.board[fx.target_row][fx.target_col]
    target_id = id_map.get((fx.target_row, fx.target_col)) if target is not None else None
    target_hp_before = target.current_hp if target is not None else 0
    target_hp_after = max(0, target_hp_before - fx.damage) if target is not None else 0
    was_captured = target_hp_after <= 0 if target is not None else False

    return {
        "turn": old_state.turn_number,
        "player": player.name,
        "action_type": "foresight_resolve",
        "piece_id": caster_id,
        "result": {
            "target_row": fx.target_row,
            "target_col": fx.target_col,
            "damage": fx.damage,
            "target_piece_id": target_id,
            "target_hp_before": target_hp_before,
            "target_hp_after": target_hp_after,
            "captured": was_captured,
        },
    }


# ---------------------------------------------------------------------------
# Per-action-type builders
# ---------------------------------------------------------------------------

def _build_move(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    entry: dict = {
        "turn": turn,
        "player": player,
        "action_type": "move",
        "piece_id": piece_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {},
    }
    # Check if this is a safetyball storing an ally
    if piece.piece_type in SAFETYBALL_TYPES:
        target = old_state.board[move.target_row][move.target_col]
        if target is not None and target.team == piece.team:
            stored_id = id_map.get((move.target_row, move.target_col))
            entry["result"] = {
                "stored": True,
                "stored_piece_id": stored_id,
                "stored_hp": target.current_hp,
                "stored_max_hp": target.max_hp,
            }
    return entry


def _build_attack(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    target = old_state.board[move.target_row][move.target_col]
    target_id = id_map.get((move.target_row, move.target_col))
    damage, type_mult = _calc_damage(piece, target, move.move_slot)
    hp_before = target.current_hp
    hp_after = max(0, hp_before - damage)
    return {
        "turn": turn,
        "player": player,
        "action_type": "attack",
        "piece_id": piece_id,
        "target_piece_id": target_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "damage": damage,
            "type_multiplier": type_mult,
            "target_hp_before": hp_before,
            "target_hp_after": hp_after,
            "captured": hp_after <= 0,
        },
    }


def _build_pokeball_attack(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
    rng_roll: Optional[float], captured: Optional[bool],
) -> dict:
    target_id = id_map.get((move.target_row, move.target_col))
    return {
        "turn": turn,
        "player": player,
        "action_type": "pokeball_attack",
        "piece_id": piece_id,
        "target_piece_id": target_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "rng_roll": rng_roll,
            "captured": captured if captured is not None else False,
            "pokeball_spent": True,
        },
    }


def _build_masterball_attack(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    target_id = id_map.get((move.target_row, move.target_col))
    return {
        "turn": turn,
        "player": player,
        "action_type": "masterball_attack",
        "piece_id": piece_id,
        "target_piece_id": target_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "captured": True,
        },
    }


def _build_quick_attack(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    target = old_state.board[move.target_row][move.target_col]
    target_id = id_map.get((move.target_row, move.target_col))
    damage, type_mult = _calc_damage(piece, target)
    hp_before = target.current_hp
    hp_after = max(0, hp_before - damage)
    return {
        "turn": turn,
        "player": player,
        "action_type": "quick_attack",
        "piece_id": piece_id,
        "target_piece_id": target_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "attack_to_row": move.target_row,
        "attack_to_col": move.target_col,
        "move_to_row": move.secondary_row,
        "move_to_col": move.secondary_col,
        "result": {
            "damage": damage,
            "type_multiplier": type_mult,
            "target_hp_before": hp_before,
            "target_hp_after": hp_after,
            "captured": hp_after <= 0,
        },
    }


def _build_foresight(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int,
) -> dict:
    damage = _FORESIGHT_DAMAGE.get(piece.piece_type, 80)
    return {
        "turn": turn,
        "player": player,
        "action_type": "foresight",
        "piece_id": piece_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "target_row": move.target_row,
            "target_col": move.target_col,
            "damage": damage,
            "resolves_on_turn": old_state.turn_number + 2,
        },
    }


def _build_evolve(
    old_state: GameState, new_state: GameState,
    piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int,
) -> dict:
    new_piece = new_state.board[move.target_row][move.target_col]
    from_species = piece.piece_type.name
    to_species = new_piece.piece_type.name if new_piece else from_species
    hp_restored = (new_piece.current_hp - piece.current_hp) if new_piece else 0
    return {
        "turn": turn,
        "player": player,
        "action_type": "evolve",
        "piece_id": piece_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "from_species": from_species,
            "to_species": to_species,
            "hp_restored": max(0, hp_restored),
        },
    }


def _build_trade(
    old_state: GameState, new_state: GameState,
    piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    target = old_state.board[move.target_row][move.target_col]
    target_id = id_map.get((move.target_row, move.target_col))
    item_given = piece.held_item.name
    item_received = target.held_item.name

    # Check if trade triggered an Eevee auto-evolution
    new_target = new_state.board[move.target_row][move.target_col]
    triggered = False
    evolved_to = None
    if new_target is not None and new_target.piece_type != target.piece_type:
        triggered = True
        evolved_to = new_target.piece_type.name

    return {
        "turn": turn,
        "player": player,
        "action_type": "trade",
        "piece_id": piece_id,
        "target_piece_id": target_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "to_row": move.target_row,
        "to_col": move.target_col,
        "result": {
            "item_given": item_given,
            "item_received": item_received,
            "triggered_evolution": triggered,
            "evolved_to": evolved_to,
        },
    }


def _build_release(
    old_state: GameState, piece: Piece, move: Move,
    piece_id: Optional[str], player: str, turn: int, id_map: IdMap,
) -> dict:
    stored = piece.stored_piece
    released_id = id_map.get(("stored", (piece.row, piece.col)))
    released_hp = stored.current_hp if stored else 0
    return {
        "turn": turn,
        "player": player,
        "action_type": "release",
        "piece_id": piece_id,
        "from_row": move.piece_row,
        "from_col": move.piece_col,
        "result": {
            "released_piece_id": released_id,
            "released_hp": released_hp,
        },
    }
