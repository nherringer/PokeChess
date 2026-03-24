"""
Move execution, damage resolution, stochastic outcomes, and win condition.

apply_move(state, move) returns one or more (resulting_state, probability) tuples.
Most moves are deterministic and return a single tuple with probability 1.0.
Pokeball interactions return two tuples: (capture_state, 0.5), (fail_state, 0.5)
— or a single (state, 1.0) if the target is immune (Pikachu/Raichu).

is_terminal(state) returns (is_done, winner) where winner is Team or None (draw).
"""

from __future__ import annotations
import dataclasses
from typing import Optional

from .state import (
    GameState, Piece, PieceType, Team, Item,
    PIECE_STATS, KING_TYPES, MATCHUP, ForesightEffect,
)
from .moves import Move, ActionType


# ---------------------------------------------------------------------------
# Damage tables
# ---------------------------------------------------------------------------

# Base damage per attacker type. All multiples of 20 so that ×0.5 / ×2.0
# matchup multipliers always produce exact multiples of 10 (matching the HP granularity).
_BASE_DAMAGE: dict[PieceType, int] = {
    PieceType.SQUIRTLE:   100,
    PieceType.CHARMANDER: 100,
    PieceType.BULBASAUR:  100,
    PieceType.PIKACHU:    80,
    PieceType.RAICHU:    100,
    PieceType.EEVEE:      40,
    PieceType.VAPOREON:   80,
    PieceType.FLAREON:    80,
    PieceType.LEAFEON:    80,
    PieceType.JOLTEON:    80,
    PieceType.ESPEON:     80,
}

# Mew's four escalating move slots.
# Slot 3 = 200 guarantees a one-shot on any 200 HP starter at neutral matchup (Psychic = 1.0×).
_MEW_SLOT_DAMAGE: dict[int, int] = {0: 40, 1: 80, 2: 120, 3: 200}

# Pre-calculated Foresight damage (applied when the effect resolves, not when cast).
_FORESIGHT_DAMAGE: dict[PieceType, int] = {
    PieceType.MEW:    120,
    PieceType.ESPEON:  80,
}

# Pokeball capture probability (Masterball = 1.0, regular pokeball = 0.5).
_POKEBALL_CAPTURE_PROB = 0.5

# Eevee evolution move_slot index → resulting PieceType (mirrors moves._EEVEE_EVOLUTION_SLOT).
_EEVEE_EVOLUTIONS: list[PieceType] = [
    PieceType.VAPOREON,   # slot 0
    PieceType.FLAREON,    # slot 1
    PieceType.LEAFEON,    # slot 2
    PieceType.JOLTEON,    # slot 3
    PieceType.ESPEON,     # slot 4
]

# Piece types that are immune to regular Pokeball capture.
_POKEBALL_IMMUNE: frozenset[PieceType] = frozenset({PieceType.PIKACHU, PieceType.RAICHU})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_move(state: GameState, move: Move) -> list[tuple[GameState, float]]:
    """
    Apply move to state. Returns list of (new_state, probability) pairs.
    Deterministic moves return a single pair with probability 1.0.
    Pokeball attacks return two pairs at p=0.5 each (capture / fail).
    """
    new = state.copy()

    # Foresight for the active player resolves at the START of their turn,
    # before the chosen move is executed.
    _resolve_foresight(new)

    # Reset the "used Foresight last turn" flag; will be re-set if this move is FORESIGHT.
    new.foresight_used_last_turn[new.active_player] = False

    piece = new.board[move.piece_row][move.piece_col]

    # --- Pokeball capture: the only stochastic action ---
    if move.action_type == ActionType.ATTACK and piece.piece_type == PieceType.POKEBALL:
        target = new.board[move.target_row][move.target_col]
        if target.piece_type in _POKEBALL_IMMUNE:
            # Immune target — deterministic failure (turn is still consumed).
            _advance_turn(new)
            return [(new, 1.0)]
        # Build a separate fail state (target survives, nothing else changes).
        fail = state.copy()
        _resolve_foresight(fail)
        fail.foresight_used_last_turn[fail.active_player] = False
        _advance_turn(fail)
        # Apply capture to the success branch (new).
        _capture(new, piece, move.target_row, move.target_col)
        _advance_turn(new)
        return [(new, _POKEBALL_CAPTURE_PROB), (fail, 1.0 - _POKEBALL_CAPTURE_PROB)]

    # --- All deterministic actions ---
    _apply_deterministic(new, piece, move)
    _advance_turn(new)
    return [(new, 1.0)]


def is_terminal(state: GameState) -> tuple[bool, Optional[Team]]:
    """
    Returns (True, winner) if a king has been eliminated, else (False, None).
    A draw (both kings gone simultaneously) returns (True, None).
    """
    red_alive  = any(p.is_king for p in state.all_pieces(Team.RED))
    blue_alive = any(p.is_king for p in state.all_pieces(Team.BLUE))
    if red_alive and blue_alive:
        return False, None
    if not red_alive and not blue_alive:
        return True, None   # simultaneous elimination = draw
    return True, Team.BLUE if not red_alive else Team.RED


_PAWN_HP_VALUE: dict[PieceType, int] = {
    PieceType.POKEBALL:   50,
    PieceType.MASTERBALL: 200,
}


def hp_winner(state: GameState) -> Optional[Team]:
    """
    Tiebreaker when the rollout depth limit is hit.
    Sums HP across all pieces; Pokeball = 50, Masterball = 200, others = current_hp.
    Returns the leading team or None for a tie.
    """
    def _team_hp(team: Team) -> int:
        return sum(
            _PAWN_HP_VALUE.get(p.piece_type, p.current_hp)
            for p in state.all_pieces(team)
        )

    red_hp  = _team_hp(Team.RED)
    blue_hp = _team_hp(Team.BLUE)
    if red_hp > blue_hp:
        return Team.RED
    if blue_hp > red_hp:
        return Team.BLUE
    return None


# ---------------------------------------------------------------------------
# Turn management
# ---------------------------------------------------------------------------

def _advance_turn(state: GameState) -> None:
    """Flip the active player and increment turn_number on every half-move."""
    state.active_player = Team.BLUE if state.active_player == Team.RED else Team.RED
    state.turn_number += 1


# ---------------------------------------------------------------------------
# Foresight resolution
# ---------------------------------------------------------------------------

def _resolve_foresight(state: GameState) -> None:
    """
    Apply the active player's pending Foresight damage if it resolves this turn.
    Foresight resolves when resolves_on_turn == state.turn_number.
    If the target square is empty the attack misses silently.
    """
    fx = state.pending_foresight[state.active_player]
    if fx is None or fx.resolves_on_turn != state.turn_number:
        return
    target = state.board[fx.target_row][fx.target_col]
    if target is not None:
        target.current_hp -= fx.damage
        if target.current_hp <= 0:
            state.board[fx.target_row][fx.target_col] = None
    state.pending_foresight[state.active_player] = None


# ---------------------------------------------------------------------------
# Deterministic action dispatch
# ---------------------------------------------------------------------------

def _apply_deterministic(state: GameState, piece: Piece, move: Move) -> None:
    at = move.action_type
    if at == ActionType.MOVE:
        _do_move(state, piece, move)
    elif at == ActionType.ATTACK:
        _do_attack(state, piece, move)
    elif at == ActionType.FORESIGHT:
        _do_foresight(state, piece, move)
    elif at == ActionType.TRADE:
        _do_trade(state, piece, move)
    elif at == ActionType.EVOLVE:
        _do_evolve(state, piece, move)
    elif at == ActionType.QUICK_ATTACK:
        _do_quick_attack(state, piece, move)


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------

def _do_move(state: GameState, piece: Piece, move: Move) -> None:
    state.board[piece.row][piece.col] = None
    piece.row, piece.col = move.target_row, move.target_col
    state.board[piece.row][piece.col] = piece
    if piece.is_pawn:
        _check_promotion(state, piece)


def _do_attack(state: GameState, piece: Piece, move: Move) -> None:
    target = state.board[move.target_row][move.target_col]
    if target is None:
        return
    if piece.piece_type == PieceType.MASTERBALL:
        _capture(state, piece, move.target_row, move.target_col)
    else:
        damage = _calc_damage(piece, target, move.move_slot)
        target.current_hp -= damage
        if target.current_hp <= 0:
            _capture(state, piece, move.target_row, move.target_col)


def _do_foresight(state: GameState, piece: Piece, move: Move) -> None:
    damage = _FORESIGHT_DAMAGE.get(piece.piece_type, 80)
    state.pending_foresight[state.active_player] = ForesightEffect(
        target_row=move.target_row,
        target_col=move.target_col,
        damage=damage,
        resolves_on_turn=state.turn_number + 2,
    )
    state.foresight_used_last_turn[state.active_player] = True


def _do_trade(state: GameState, piece: Piece, move: Move) -> None:
    target = state.board[move.target_row][move.target_col]
    piece.held_item, target.held_item = target.held_item, piece.held_item


def _do_evolve(state: GameState, piece: Piece, move: Move) -> None:
    if piece.piece_type == PieceType.PIKACHU:
        hp_gain = PIECE_STATS[PieceType.RAICHU].max_hp - PIECE_STATS[PieceType.PIKACHU].max_hp
        piece.piece_type = PieceType.RAICHU
        piece.current_hp = min(piece.current_hp + hp_gain, PIECE_STATS[PieceType.RAICHU].max_hp)
        piece.held_item = Item.NONE  # Thunderstone consumed by evolution
    elif piece.piece_type == PieceType.EEVEE:
        evo = _EEVEE_EVOLUTIONS[move.move_slot]
        hp_gain = PIECE_STATS[evo].max_hp - PIECE_STATS[PieceType.EEVEE].max_hp
        piece.piece_type = evo
        piece.current_hp = min(piece.current_hp + hp_gain, PIECE_STATS[evo].max_hp)
        piece.held_item = Item.NONE  # Evolution stone consumed


def _do_quick_attack(state: GameState, piece: Piece, move: Move) -> None:
    # Step 1: Move Eevee to the intermediate destination.
    state.board[piece.row][piece.col] = None
    piece.row, piece.col = move.target_row, move.target_col
    state.board[piece.row][piece.col] = piece
    # Step 2: Attack from the new position.
    target = state.board[move.secondary_row][move.secondary_col]
    if target is not None:
        damage = _calc_damage(piece, target)
        target.current_hp -= damage
        if target.current_hp <= 0:
            _capture(state, piece, move.secondary_row, move.secondary_col)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _capture(state: GameState, attacker: Piece, target_row: int, target_col: int) -> None:
    """Remove the target; attacker occupies the vacated square."""
    state.board[target_row][target_col] = None
    state.board[attacker.row][attacker.col] = None
    attacker.row, attacker.col = target_row, target_col
    state.board[target_row][target_col] = attacker
    if attacker.is_pawn:
        _check_promotion(state, attacker)


def _check_promotion(state: GameState, piece: Piece) -> None:
    """Pokeball reaching the opponent's back rank promotes to Masterball."""
    promo_row = 7 if piece.team == Team.RED else 0
    if piece.row == promo_row and piece.piece_type == PieceType.POKEBALL:
        piece.piece_type = PieceType.MASTERBALL


def _calc_damage(attacker: Piece, target: Piece, move_slot: Optional[int] = None) -> int:
    """
    Compute damage dealt by attacker to target.

    Formula: round(base × type_mult × item_mult) to nearest 10, min 10.
    - base: from _BASE_DAMAGE or _MEW_SLOT_DAMAGE
    - type_mult: from MATCHUP[attacker_type][target_type]
    - item_mult: 1.5 if held item boosts attacker's own type, else 1.0
    """
    if attacker.piece_type == PieceType.MEW:
        base = _MEW_SLOT_DAMAGE.get(move_slot, _MEW_SLOT_DAMAGE[0])
    else:
        base = _BASE_DAMAGE.get(attacker.piece_type, 60)

    type_mult = MATCHUP[attacker.pokemon_type][target.pokemon_type]

    raw = base * type_mult
    return max(10, int(round(raw / 10)) * 10)
