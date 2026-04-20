"""
Move execution, damage resolution, stochastic outcomes, and win condition.

apply_move(state, move) returns one or more (resulting_state, probability) tuples.
Most moves are deterministic and return a single tuple with probability 1.0.
Pokeball interactions return two tuples at variable probabilities (capture / fail)
based on target HP — or a single (state, 1.0) if the target is immune.

is_terminal(state) returns (is_done, winner) where winner is Team or None (draw).
"""

from __future__ import annotations
import dataclasses
from typing import Optional

from .state import (
    GameState, Piece, PieceType, PokemonType, Team, Item,
    PIECE_STATS, KING_TYPES, MATCHUP, ForesightEffect, PAWN_TYPES, SAFETYBALL_TYPES,
    TALL_GRASS_ROWS, FloorItem,
)
from .moves import Move, ActionType, nearest_open_drop_squares


# ---------------------------------------------------------------------------
# Damage tables
# ---------------------------------------------------------------------------

_BASE_DAMAGE: dict[PieceType, int] = {
    PieceType.SQUIRTLE:   100,
    PieceType.CHARMANDER: 100,
    PieceType.BULBASAUR:  100,
    PieceType.PIKACHU:    100,
    PieceType.RAICHU:     100,
    PieceType.EEVEE:       50,
    PieceType.VAPOREON:   100,
    PieceType.FLAREON:    180,  # Flare Blitz base damage
    PieceType.LEAFEON:    100,
    PieceType.JOLTEON:    100,
    PieceType.ESPEON:      80,
}

_MEW_SLOT_TYPES: dict[int, PokemonType] = {
    0: PokemonType.FIRE,
    1: PokemonType.WATER,
    2: PokemonType.GRASS,
}

_FORESIGHT_DAMAGE: dict[PieceType, int] = {
    PieceType.MEW:    120,
    PieceType.ESPEON: 120,
}

_EEVEE_EVOLUTIONS: list[PieceType] = [
    PieceType.VAPOREON,
    PieceType.FLAREON,
    PieceType.LEAFEON,
    PieceType.JOLTEON,
    PieceType.ESPEON,
]

_POKEBALL_IMMUNE: frozenset[PieceType] = frozenset({PieceType.PIKACHU})

_FLAREON_RECOIL = 40


# ---------------------------------------------------------------------------
# Variable catch rates
# ---------------------------------------------------------------------------

def _pokeball_catch_prob(target: Piece) -> float:
    """
    HP-based catch rate for a standard Stealball.
    Mew has lower rates than all other targets.
    """
    ratio = target.current_hp / target.max_hp if target.max_hp > 0 else 1.0
    if target.piece_type == PieceType.MEW:
        if ratio >= 1.0:
            return 0.20
        if ratio >= 0.5:
            return 0.40
        return 0.60
    else:
        if ratio >= 1.0:
            return 0.25
        if ratio >= 0.5:
            return 0.50
        return 0.75


# ---------------------------------------------------------------------------
# Helper: detect forward Healball entry
# ---------------------------------------------------------------------------

def _find_storing_safetyball(state: GameState, piece: Piece) -> Optional[Piece]:
    """
    Return the Safetyball that has `piece` stored inside it, or None.
    Used to detect forward Healball entry so discharge treats the Safetyball
    as the effective moved piece (preventing immediate expulsion of the piece).
    """
    for row in state.board:
        for p in row:
            if p is not None and p.stored_piece is piece:
                return p
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_move(state: GameState, move: Move) -> list[tuple[GameState, float]]:
    """
    Apply move to state. Returns list of (new_state, probability) pairs.
    Deterministic moves return a single pair with probability 1.0.
    Pokeball attacks return two pairs at variable probabilities (capture / fail).
    """
    new = state.copy()

    _resolve_foresight(new)
    new.foresight_used_last_turn[new.active_player] = False

    piece = new.board[move.piece_row][move.piece_col]

    # --- Pokeball capture: the only stochastic action ---
    if move.action_type == ActionType.ATTACK and piece.piece_type == PieceType.POKEBALL:
        target = new.board[move.target_row][move.target_col]
        if target is None:
            new.has_traded[new.active_player] = False
            _discharge_unmoved_safetyballs(new, piece)
            _advance_turn(new)
            return [(new, 1.0)]
        if target.piece_type in _POKEBALL_IMMUNE or target.piece_type in SAFETYBALL_TYPES:
            new.has_traded[new.active_player] = False
            _discharge_unmoved_safetyballs(new, piece)
            _advance_turn(new)
            return [(new, 1.0)]
        prob = _pokeball_catch_prob(target)
        # Build fail state: pokeball spent, target survives, item dropped on capture square.
        fail = state.copy()
        _resolve_foresight(fail)
        fail.foresight_used_last_turn[fail.active_player] = False
        fail.has_traded[fail.active_player] = False
        fail_piece = fail.board[move.piece_row][move.piece_col]
        fail.board[move.piece_row][move.piece_col] = None
        _discharge_unmoved_safetyballs(fail, fail_piece)
        _advance_turn(fail)
        # Success branch: both disappear; item drops at capture square.
        _capture_both(new, piece, move.target_row, move.target_col)
        new.has_traded[new.active_player] = False
        _discharge_unmoved_safetyballs(new, piece)
        _advance_turn(new)
        return [(new, prob), (fail, 1.0 - prob)]

    # --- TRADE: free action (does not consume turn) ---
    if move.action_type == ActionType.TRADE:
        ends_turn = _do_trade(new, piece, move)
        if ends_turn:
            new.has_traded[new.active_player] = False
            _discharge_unmoved_safetyballs(new, piece)
            _advance_turn(new)
        else:
            new.has_traded[new.active_player] = True
        return [(new, 1.0)]

    # --- All deterministic actions ---
    _apply_deterministic(new, piece, move)
    new.has_traded[new.active_player] = False
    # If piece entered a Safetyball this turn (forward entry), treat the Safetyball
    # as the "moved" piece so discharge doesn't expel the just-stored Pokemon.
    discharge_piece = _find_storing_safetyball(new, piece) or piece
    _discharge_unmoved_safetyballs(new, discharge_piece)
    _advance_turn(new)
    return [(new, 1.0)]


def is_terminal(state: GameState) -> tuple[bool, Optional[Team]]:
    """
    Returns (True, winner) if a king has been eliminated, else (False, None).
    Kings stored inside safetyballs count as alive.
    """
    red_alive  = any(p.is_king for p in state.all_pieces(Team.RED))
    blue_alive = any(p.is_king for p in state.all_pieces(Team.BLUE))
    if not red_alive or not blue_alive:
        for p in state.all_pieces():
            if p.stored_piece is not None and p.stored_piece.is_king:
                if p.stored_piece.team == Team.RED:
                    red_alive = True
                else:
                    blue_alive = True
    if red_alive and blue_alive:
        return False, None
    if not red_alive and not blue_alive:
        return True, None
    return True, Team.BLUE if not red_alive else Team.RED


_PAWN_HP_VALUE: dict[PieceType, int] = {
    PieceType.POKEBALL:          50,
    PieceType.MASTERBALL:        200,
    PieceType.SAFETYBALL:        50,
    PieceType.MASTER_SAFETYBALL: 200,
}


def hp_winner(state: GameState) -> Optional[Team]:
    """
    Tiebreaker when the rollout depth limit is hit.
    Sums HP across all pieces; Pokeball = 50, Masterball = 200, others = current_hp.
    """
    def _team_hp(team: Team) -> int:
        total = 0
        for p in state.all_pieces(team):
            total += _PAWN_HP_VALUE.get(p.piece_type, p.current_hp)
            if p.stored_piece is not None:
                total += p.stored_piece.current_hp
        return total

    red_hp  = _team_hp(Team.RED)
    blue_hp = _team_hp(Team.BLUE)
    if red_hp > blue_hp:
        return Team.RED
    if blue_hp > red_hp:
        return Team.BLUE
    return None


# ---------------------------------------------------------------------------
# Attempt-capture stub (reserved for Wild Pokemon update)
# ---------------------------------------------------------------------------

def attempt_capture(pokeball: Piece, target: Piece) -> None:
    raise NotImplementedError("Capture logic reserved for Wild Pokemon update")


# ---------------------------------------------------------------------------
# Turn management
# ---------------------------------------------------------------------------

def _advance_turn(state: GameState) -> None:
    state.active_player = Team.BLUE if state.active_player == Team.RED else Team.RED
    state.turn_number += 1


# ---------------------------------------------------------------------------
# Foresight resolution
# ---------------------------------------------------------------------------

def _resolve_foresight(state: GameState) -> None:
    """
    Apply the active player's pending Foresight damage if it resolves this turn.
    Foresight fizzles on any PAWN_TYPE target (Stealballs and Healballs).
    """
    fx = state.pending_foresight[state.active_player]
    if fx is None or fx.resolves_on_turn != state.turn_number:
        return
    target = state.board[fx.target_row][fx.target_col]
    if target is not None and target.piece_type not in PAWN_TYPES:
        target.current_hp -= fx.damage
        if target.current_hp <= 0:
            if target.held_item != Item.NONE:
                state.floor_items.append(
                    FloorItem(row=fx.target_row, col=fx.target_col, item=target.held_item)
                )
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
    elif at == ActionType.EVOLVE:
        _do_evolve(state, piece, move)
    elif at == ActionType.QUICK_ATTACK:
        _do_quick_attack(state, piece, move)
    elif at == ActionType.RELEASE:
        _do_release(state, piece, move)
    elif at == ActionType.PSYWAVE:
        _do_psywave(state, piece, move)


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------

def _do_move(state: GameState, piece: Piece, move: Move) -> None:
    from_r, from_c = piece.row, piece.col
    state.board[from_r][from_c] = None
    old_target = state.board[move.target_row][move.target_col]

    # Pokemon-enters-Healball (forward entry mechanic — piece moves into a Healball).
    if (
        not piece.is_pawn
        and piece.piece_type != PieceType.PIKACHU
        and piece.current_hp < piece.max_hp
        and old_target is not None
        and old_target.piece_type in SAFETYBALL_TYPES
        and old_target.team == piece.team
        and old_target.stored_piece is None
    ):
        # Healball stays at target; piece is stored inside it.
        state.board[move.target_row][move.target_col] = old_target
        old_target.stored_piece = piece
        _safetyball_heal(state, old_target)
        return

    piece.row, piece.col = move.target_row, move.target_col
    state.board[piece.row][piece.col] = piece

    if piece.is_pawn:
        _check_promotion(state, piece)

    # Tall grass exploration for non-pawn pieces.
    if (
        not piece.is_pawn
        and piece.row in TALL_GRASS_ROWS
        and (piece.row, piece.col) not in state.tall_grass_explored
    ):
        _explore_tall_grass(state, piece, move)

    # Floor item pickup for non-pawn pieces.
    if not piece.is_pawn:
        for i, fi in enumerate(state.floor_items):
            if fi.row == piece.row and fi.col == piece.col:
                state.floor_items.pop(i)
                _handle_item_encounter(state, piece, fi.item, move, from_r, from_c)
                break

    # Safetyball-absorbs-injured-ally and heal-while-carrying.
    if piece.piece_type in SAFETYBALL_TYPES:
        if old_target is not None and old_target.team == piece.team:
            piece.stored_piece = old_target
            _safetyball_heal(state, piece)
        elif piece.stored_piece is not None:
            _safetyball_heal(state, piece)


def _do_attack(state: GameState, piece: Piece, move: Move) -> None:
    target = state.board[move.target_row][move.target_col]
    if target is None:
        return
    if target.piece_type in SAFETYBALL_TYPES:
        return
    if piece.piece_type == PieceType.MASTERBALL:
        _capture_both(state, piece, move.target_row, move.target_col)
    elif target.piece_type in PAWN_TYPES:
        if piece.piece_type in _POKEBALL_IMMUNE and target.piece_type == PieceType.POKEBALL:
            _capture(state, piece, move.target_row, move.target_col, move)
        else:
            _capture_both(state, piece, move.target_row, move.target_col)
    else:
        damage = _calc_damage(piece, target, move.move_slot)
        target.current_hp -= damage
        if target.current_hp <= 0:
            _capture(state, piece, move.target_row, move.target_col, move)
        # Flareon Flare Blitz recoil: 40 self-damage after every regular ATTACK.
        if piece.piece_type == PieceType.FLAREON:
            piece.current_hp -= _FLAREON_RECOIL
            if piece.current_hp <= 0:
                if piece.held_item != Item.NONE:
                    state.floor_items.append(
                        FloorItem(row=piece.row, col=piece.col, item=piece.held_item)
                    )
                state.board[piece.row][piece.col] = None


def _do_foresight(state: GameState, piece: Piece, move: Move) -> None:
    damage = _FORESIGHT_DAMAGE.get(piece.piece_type, 80)
    state.pending_foresight[state.active_player] = ForesightEffect(
        target_row=move.target_row,
        target_col=move.target_col,
        damage=damage,
        resolves_on_turn=state.turn_number + 2,
        caster_row=move.piece_row,
        caster_col=move.piece_col,
    )
    state.foresight_used_last_turn[state.active_player] = True


def _do_trade(state: GameState, piece: Piece, move: Move) -> bool:
    """Swap held items. Returns True if the trade ends the turn."""
    target = state.board[move.target_row][move.target_col]
    piece.held_item, target.held_item = target.held_item, piece.held_item
    return False


def _do_evolve(state: GameState, piece: Piece, move: Move) -> None:
    if piece.piece_type == PieceType.PIKACHU:
        hp_gain = PIECE_STATS[PieceType.RAICHU].max_hp - PIECE_STATS[PieceType.PIKACHU].max_hp
        piece.piece_type = PieceType.RAICHU
        piece.current_hp = min(piece.current_hp + hp_gain, PIECE_STATS[PieceType.RAICHU].max_hp)
        piece.held_item = Item.NONE
    elif piece.piece_type == PieceType.EEVEE:
        evo = _EEVEE_EVOLUTIONS[move.move_slot]
        hp_gain = PIECE_STATS[evo].max_hp - PIECE_STATS[PieceType.EEVEE].max_hp
        piece.piece_type = evo
        piece.current_hp = min(piece.current_hp + hp_gain, PIECE_STATS[evo].max_hp)
        piece.held_item = Item.NONE


def _do_release(state: GameState, piece: Piece, move: Move) -> None:
    """Place the stored Pokémon on the Safetyball's square; Safetyball is consumed."""
    stored = piece.stored_piece
    stored.row, stored.col = piece.row, piece.col
    state.board[piece.row][piece.col] = stored
    # Explore tall grass on landing.
    if stored.row in TALL_GRASS_ROWS and (stored.row, stored.col) not in state.tall_grass_explored:
        _explore_tall_grass(state, stored, move=None)
    # Pick up floor item on landing.
    for i, fi in enumerate(state.floor_items):
        if fi.row == stored.row and fi.col == stored.col:
            state.floor_items.pop(i)
            _handle_item_encounter(state, stored, fi.item, None, stored.row, stored.col)
            break


def _discharge_unmoved_safetyballs(state: GameState, moved_piece: Piece) -> None:
    """
    If the active player did NOT move a safetyball this turn, auto-release any
    stored Pokémon from their safetyballs back to the board.
    """
    if moved_piece.piece_type in SAFETYBALL_TYPES:
        return
    for p in list(state.all_pieces(state.active_player)):
        if p.piece_type in SAFETYBALL_TYPES and p.stored_piece is not None:
            stored = p.stored_piece
            stored.row, stored.col = p.row, p.col
            state.board[p.row][p.col] = stored
            p.stored_piece = None
            # Expelled pokemon explores tall grass on landing.
            if stored.row in TALL_GRASS_ROWS and (stored.row, stored.col) not in state.tall_grass_explored:
                _explore_tall_grass(state, stored, move=None)
            # Pick up floor item on landing.
            for i, fi in enumerate(state.floor_items):
                if fi.row == stored.row and fi.col == stored.col:
                    state.floor_items.pop(i)
                    _handle_item_encounter(state, stored, fi.item, None, stored.row, stored.col)
                    break


def _safetyball_heal(state: GameState, piece: Piece) -> None:
    """
    Heal the stored Pokémon.
    - Master Safetyball: restore to full HP immediately, no auto-release.
    - Basic Safetyball: heal ¼ max HP; auto-release when full.
    """
    stored = piece.stored_piece
    if piece.piece_type == PieceType.MASTER_SAFETYBALL:
        already_full = stored.current_hp >= stored.max_hp
        stored.current_hp = stored.max_hp
        if already_full:
            # Stored piece was already full (healed on entry last turn) — auto-release.
            stored.row, stored.col = piece.row, piece.col
            state.board[piece.row][piece.col] = stored
            piece.stored_piece = None
    else:
        stored.current_hp = min(stored.current_hp + stored.max_hp // 4, stored.max_hp)
        if stored.current_hp >= stored.max_hp:
            stored.row, stored.col = piece.row, piece.col
            state.board[piece.row][piece.col] = stored


def _do_quick_attack(state: GameState, piece: Piece, move: Move) -> None:
    target = state.board[move.target_row][move.target_col]
    if target is not None:
        damage = _calc_damage(piece, target)
        target.current_hp -= damage
        if target.current_hp <= 0:
            _capture(state, piece, move.target_row, move.target_col, move)
    if move.secondary_row is not None and move.secondary_col is not None:
        state.board[piece.row][piece.col] = None
        piece.row, piece.col = move.secondary_row, move.secondary_col
        state.board[piece.row][piece.col] = piece


def _do_psywave(state: GameState, piece: Piece, move: Move) -> None:
    """
    Espeon's Psywave: fire along all 8 queen directions simultaneously.
    Each ray stops at the first obstacle.
    - Non-Psychic Pokemon: take max(10, 80 - 10*n) damage (n = empty squares).
    - Psychic-type Pokemon, Stealballs, Healballs: stop ray, no damage.
    """
    dirs = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
    for dr, dc in dirs:
        n = 0
        r, c = piece.row + dr, piece.col + dc
        while _in_bounds(r, c):
            target = state.board[r][c]
            if target is not None:
                if target.piece_type in PAWN_TYPES:
                    break  # all pawns block ray, no damage
                if target.pokemon_type == PokemonType.PSYCHIC:
                    break  # Psychic-type blocks ray, no damage
                damage = max(10, 80 - 10 * n)
                target.current_hp -= damage
                if target.current_hp <= 0:
                    if target.held_item != Item.NONE:
                        state.floor_items.append(
                            FloorItem(row=r, col=c, item=target.held_item)
                        )
                    state.board[r][c] = None
                break
            n += 1
            r += dr
            c += dc


# ---------------------------------------------------------------------------
# Tall grass and item helpers
# ---------------------------------------------------------------------------

def _explore_tall_grass(state: GameState, piece: Piece, move: Optional[Move]) -> None:
    """Mark a tall grass square as explored; auto-pick up any hidden item found."""
    r, c = piece.row, piece.col
    state.tall_grass_explored.add((r, c))
    for i, hi in enumerate(state.hidden_items):
        if hi.row == r and hi.col == c:
            state.hidden_items.pop(i)
            _handle_item_encounter(state, piece, hi.item, move, r, c)
            break


def _handle_item_encounter(
    state: GameState,
    piece: Piece,
    item: Item,
    move: Optional[Move],
    from_row: Optional[int] = None,
    from_col: Optional[int] = None,
) -> None:
    """
    Handle a piece picking up an item.
    If piece is empty-handed: auto-pickup.
    Otherwise overflow: use move.overflow_* fields if present, else default
    (keep existing item, drop new item at first nearest open square row-major).
    """
    if piece.held_item == Item.NONE:
        piece.held_item = item
        return

    keep = move.overflow_keep if move is not None else None
    drop_r = move.overflow_drop_row if move is not None else None
    drop_c = move.overflow_drop_col if move is not None else None

    if keep == 'existing' and drop_r is not None:
        state.floor_items.append(FloorItem(row=drop_r, col=drop_c, item=item))
    elif keep == 'new' and drop_r is not None:
        dropped = piece.held_item
        piece.held_item = item
        state.floor_items.append(FloorItem(row=drop_r, col=drop_c, item=dropped))
    else:
        # Default (bot / server path): keep existing, drop new at first open square row-major.
        fr = from_row if from_row is not None else piece.row
        fc = from_col if from_col is not None else piece.col
        drops = nearest_open_drop_squares(state, fr, fc, piece.row, piece.col)
        if drops:
            drops.sort(key=lambda rc: (rc[0], rc[1]))
            state.floor_items.append(FloorItem(row=drops[0][0], col=drops[0][1], item=item))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _capture_both(state: GameState, attacker: Piece, target_row: int, target_col: int) -> None:
    """Remove both attacker and target. Target's item drops at capture square."""
    target = state.board[target_row][target_col]
    if target is not None and target.held_item != Item.NONE:
        state.floor_items.append(FloorItem(row=target_row, col=target_col, item=target.held_item))
    state.board[attacker.row][attacker.col] = None
    state.board[target_row][target_col] = None


def _capture(
    state: GameState,
    attacker: Piece,
    target_row: int,
    target_col: int,
    move: Optional[Move] = None,
) -> None:
    """Remove the target; attacker occupies the vacated square. Transfer target's item."""
    target = state.board[target_row][target_col]
    target_item = target.held_item if target is not None else Item.NONE
    from_r, from_c = attacker.row, attacker.col
    state.board[target_row][target_col] = None
    state.board[attacker.row][attacker.col] = None
    attacker.row, attacker.col = target_row, target_col
    state.board[target_row][target_col] = attacker
    if attacker.is_pawn:
        _check_promotion(state, attacker)
    if target_item != Item.NONE:
        _handle_item_encounter(state, attacker, target_item, move, from_r, from_c)


def _check_promotion(state: GameState, piece: Piece) -> None:
    promo_row = 7 if piece.team == Team.RED else 0
    if piece.row == promo_row:
        if piece.piece_type == PieceType.POKEBALL:
            piece.piece_type = PieceType.MASTERBALL
        elif piece.piece_type == PieceType.SAFETYBALL:
            piece.piece_type = PieceType.MASTER_SAFETYBALL


def _calc_damage(attacker: Piece, target: Piece, move_slot: Optional[int] = None) -> int:
    damage, _ = calc_damage_with_multiplier(attacker, target, move_slot)
    return damage


def calc_damage_with_multiplier(
    attacker: Piece, target: Piece, move_slot: Optional[int] = None
) -> tuple[int, float]:
    """
    Compute (damage, type_multiplier) for attacker → target.

    Formula: round(base × type_mult) to nearest 10, min 10.
    Leafeon's -40 damage reduction is applied to the attacker's base before type mult.
    """
    if attacker.piece_type == PieceType.MEW:
        base = 100
        atk_type = _MEW_SLOT_TYPES.get(move_slot, PokemonType.FIRE)
    else:
        base = _BASE_DAMAGE.get(attacker.piece_type, 60)
        atk_type = attacker.pokemon_type

    # Leafeon passive: -40 to base damage before type effectiveness, floor 1.
    if target.piece_type == PieceType.LEAFEON:
        base = max(1, base - 40)

    type_mult = MATCHUP[atk_type][target.pokemon_type]
    raw = base * type_mult
    return max(10, int(round(raw / 10)) * 10), type_mult


def _in_bounds(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8
