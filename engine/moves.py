"""
Legal move generation for all PokeChess piece types.

A Move encodes one complete action a player can take on their turn:
  - Move a piece to an empty square
  - Attack a piece in range (attacker stays unless KO)
  - Use Foresight (Mew/Espeon only)
  - Trade held items with an adjacent teammate
  - Evolve (Pikachu→Raichu or Eevee→evo, costs the turn)
  - For Eevee only: move + attack in same turn (Quick Attack)

get_legal_moves(state) returns all legal moves for the active player.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

from .state import (
    PieceType, Team, Item, PAWN_TYPES, SAFETYBALL_TYPES, MATCHUP, PokemonType,
    TALL_GRASS_ROWS,
)

if TYPE_CHECKING:
    from .state import GameState, Piece


class ActionType(Enum):
    MOVE         = auto()  # Move to empty square (or Safetyball onto injured ally)
    ATTACK       = auto()  # Attack target in movement range
    FORESIGHT    = auto()  # Delayed attack (Mew/Espeon)
    TRADE        = auto()  # Swap held items with adjacent teammate
    EVOLVE       = auto()  # Trigger evolution (costs full turn)
    QUICK_ATTACK = auto()  # Eevee/eeveelutions (not Espeon): attack then move same turn
    RELEASE      = auto()  # Safetyball: release stored Pokémon in place
    PSYWAVE      = auto()  # Espeon only: AoE radiating in all 8 queen directions


@dataclass
class Move:
    piece_row: int
    piece_col: int
    action_type: ActionType
    # Destination square (for MOVE, EVOLVE) or target square (for ATTACK, FORESIGHT, TRADE)
    target_row: int
    target_col: int
    # Quick Attack only: secondary action destination after the primary move
    secondary_row: Optional[int] = None
    secondary_col: Optional[int] = None
    # Which move slot Mew is using (0-3), None for all others
    move_slot: Optional[int] = None
    # Item overflow fields: set when picking up a second item requires a player choice.
    # overflow_keep: "existing" = keep current held item, drop new item at drop square.
    #               "new"      = keep new item, drop existing item at drop square.
    # None when no overflow encoding is needed (auto-pickup or bot default path).
    overflow_keep: Optional[str] = None
    overflow_drop_row: Optional[int] = None
    overflow_drop_col: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize this Move to a flat wire-format dict. Optional fields are null when absent."""
        return {
            "piece_row": self.piece_row,
            "piece_col": self.piece_col,
            "action_type": self.action_type.name,
            "target_row": self.target_row,
            "target_col": self.target_col,
            "secondary_row": self.secondary_row,
            "secondary_col": self.secondary_col,
            "move_slot": self.move_slot,
            "overflow_keep": self.overflow_keep,
            "overflow_drop_row": self.overflow_drop_row,
            "overflow_drop_col": self.overflow_drop_col,
        }


# --- movement geometry ---

_ROOK_DIRS    = [(0, 1), (0, -1), (1, 0), (-1, 0)]
_BISHOP_DIRS  = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_QUEEN_DIRS   = _ROOK_DIRS + _BISHOP_DIRS
_KNIGHT_JUMPS = [
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2),
]
_PIKACHU_EXTENDED_L   = [(3,1),(3,-1),(-3,1),(-3,-1),(1,3),(1,-3),(-1,3),(-1,-3)]
_JOLTEON_DIAG_JUMPS   = [(2, 2), (2, -2), (-2, 2), (-2, -2)]
_MEW_SLOTS = (0, 1, 2)

# Base damage values mirrored here for will-KO prediction in move generation.
# Authoritative values live in rules.py; keep these in sync.
_MOVEGEN_BASE_DAMAGE: dict[PieceType, int] = {
    PieceType.SQUIRTLE:   100,
    PieceType.CHARMANDER: 100,
    PieceType.BULBASAUR:  100,
    PieceType.PIKACHU:    100,
    PieceType.RAICHU:     100,
    PieceType.VAPOREON:   100,
    PieceType.FLAREON:    180,  # Flare Blitz
    PieceType.LEAFEON:    100,
    PieceType.JOLTEON:    100,
    PieceType.ESPEON:      80,
    PieceType.MEW:        100,
}

_MEW_SLOT_TYPES = {
    0: PokemonType.FIRE,
    1: PokemonType.WATER,
    2: PokemonType.GRASS,
}


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8


def _attack_damage_gen(piece: 'Piece', target: 'Piece', move_slot: Optional[int] = None) -> int:
    """Compute attack damage for will-KO prediction during move generation."""
    if piece.piece_type == PieceType.MEW:
        atk_type = _MEW_SLOT_TYPES.get(move_slot, PokemonType.FIRE)
        base = 100
    else:
        base = _MOVEGEN_BASE_DAMAGE.get(piece.piece_type, 60)
        atk_type = piece.pokemon_type
    # Leafeon -40 damage reduction applied to base before type effectiveness
    if target.piece_type == PieceType.LEAFEON:
        base = max(1, base - 40)
    mult = MATCHUP[atk_type][target.pokemon_type]
    raw = base * mult
    return max(10, int(round(raw / 10)) * 10)


def _attack_will_ko(piece: 'Piece', target: 'Piece', move_slot: Optional[int] = None) -> bool:
    return _attack_damage_gen(piece, target, move_slot) >= target.current_hp


def _is_unexplored_grass(state: 'GameState', row: int, col: int) -> bool:
    return row in TALL_GRASS_ROWS and (row, col) not in state.tall_grass_explored


def _floor_item_at(state: 'GameState', row: int, col: int) -> Optional[Item]:
    for fi in state.floor_items:
        if fi.row == row and fi.col == col:
            return fi.item
    return None


def nearest_open_drop_squares(
    state: 'GameState',
    from_row: int, from_col: int,
    to_row: int, to_col: int,
) -> list[tuple[int, int]]:
    """
    Find all open squares at minimum Chebyshev distance from (to_row, to_col),
    using the post-move board state (from square vacated, to square occupied).

    An open square is: explored (not unexplored tall grass), not occupied by a
    piece (other than the vacated from square), and has no floor item.
    """
    floor_locs = {(fi.row, fi.col) for fi in state.floor_items}

    def is_open(r: int, c: int) -> bool:
        if not _in_bounds(r, c):
            return False
        if (r, c) == (to_row, to_col):
            return False  # occupied by the moving piece after the move
        if (r, c) in floor_locs:
            return False
        if r in TALL_GRASS_ROWS and (r, c) not in state.tall_grass_explored:
            return False
        piece_at = state.board[r][c]
        if piece_at is not None and (r, c) != (from_row, from_col):
            return False  # from square is vacated by this move
        return True

    open_squares = [(r, c) for r in range(8) for c in range(8) if is_open(r, c)]
    if not open_squares:
        return []

    def cheb(r: int, c: int) -> int:
        return max(abs(r - to_row), abs(c - to_col))

    min_d = min(cheb(r, c) for r, c in open_squares)
    return [(r, c) for r, c in open_squares if cheb(r, c) == min_d]


def _overflow_variants(
    base_move: Move,
    drop_squares: list[tuple[int, int]],
) -> list[Move]:
    """For each drop square, return two overflow variants (keep existing / keep new)."""
    result = []
    for dr, dc in drop_squares:
        result.append(Move(
            base_move.piece_row, base_move.piece_col,
            base_move.action_type,
            base_move.target_row, base_move.target_col,
            secondary_row=base_move.secondary_row,
            secondary_col=base_move.secondary_col,
            move_slot=base_move.move_slot,
            overflow_keep='existing',
            overflow_drop_row=dr,
            overflow_drop_col=dc,
        ))
        result.append(Move(
            base_move.piece_row, base_move.piece_col,
            base_move.action_type,
            base_move.target_row, base_move.target_col,
            secondary_row=base_move.secondary_row,
            secondary_col=base_move.secondary_col,
            move_slot=base_move.move_slot,
            overflow_keep='new',
            overflow_drop_row=dr,
            overflow_drop_col=dc,
        ))
    return result


def _expand_overflow_moves(piece: 'Piece', state: 'GameState', moves: list[Move]) -> list[Move]:
    """
    Post-process a piece's move list to replace moves that trigger item overflow
    with enumerated (keep, drop-location) variants.

    Overflow is triggered when:
    - MOVE to an unexplored grass square, piece holds item (grass may contain item)
    - MOVE onto a floor item square, piece holds item
    - ATTACK that will KO an item-holding target, attacker also holds item
    """
    if piece.held_item == Item.NONE:
        return moves  # piece holds nothing — no overflow possible

    result = []
    for m in moves:
        if m.action_type == ActionType.MOVE:
            needs_overflow = (
                _is_unexplored_grass(state, m.target_row, m.target_col)
                or _floor_item_at(state, m.target_row, m.target_col) is not None
            )
            if needs_overflow:
                drops = nearest_open_drop_squares(
                    state, m.piece_row, m.piece_col, m.target_row, m.target_col
                )
                if drops:
                    result.extend(_overflow_variants(m, drops))
                else:
                    result.append(m)  # no valid drop — emit without overflow
            else:
                result.append(m)

        elif m.action_type == ActionType.ATTACK:
            target = state.board[m.target_row][m.target_col]
            if (
                target is not None
                and target.held_item != Item.NONE
                and _attack_will_ko(piece, target, m.move_slot)
            ):
                drops = nearest_open_drop_squares(
                    state, m.piece_row, m.piece_col, m.target_row, m.target_col
                )
                if drops:
                    result.extend(_overflow_variants(m, drops))
                else:
                    result.append(m)
            else:
                result.append(m)

        else:
            result.append(m)

    return result


def _sliding_squares(
    piece: 'Piece',
    state: 'GameState',
    directions: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Walk each direction until hitting the board edge or another piece.
    Returns (empty_squares, enemy_squares) reachable by sliding.
    Friendly pieces block the ray; enemy pieces can be attacked but not passed.
    """
    empties: list[tuple[int, int]] = []
    enemies: list[tuple[int, int]] = []
    for dr, dc in directions:
        r, c = piece.row + dr, piece.col + dc
        while _in_bounds(r, c):
            occupant = state.board[r][c]
            if occupant is None:
                empties.append((r, c))
            elif occupant.team != piece.team:
                # Enemy Safetyballs block the ray but cannot be attacked
                if occupant.piece_type not in SAFETYBALL_TYPES:
                    enemies.append((r, c))
                break
            else:
                break  # friendly blocks the ray
            r += dr
            c += dc
    return empties, enemies


def _trade_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """
    TRADE with any adjacent (including diagonal) friendly piece that holds a different item.
    Both pieces swap their held_item; only makes sense when items differ.
    """
    if state.has_traded[piece.team]:
        return []
    moves = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = piece.row + dr, piece.col + dc
            if not _in_bounds(r, c):
                continue
            neighbor = state.board[r][c]
            if (
                neighbor is not None
                and neighbor.team == piece.team
                and neighbor.piece_type not in PAWN_TYPES
                and piece.piece_type not in PAWN_TYPES
                and neighbor.held_item != piece.held_item
            ):
                moves.append(Move(piece.row, piece.col, ActionType.TRADE, r, c))
    return moves


# --- per-piece-type generators ---

def _forward(team: Team) -> int:
    """Row delta for 'forward': +1 for RED (toward row 7), -1 for BLUE (toward row 0)."""
    return 1 if team == Team.RED else -1


def _forward_healball_entry(piece: 'Piece', state: 'GameState') -> list[Move]:
    """
    Return a MOVE into the Healball directly ahead of piece, if valid.
    Valid when: square has a friendly empty Healball, piece is injured, not Pikachu,
    and storing leaves at least one other piece on the board.
    """
    fwd_row = piece.row + _forward(piece.team)
    if not _in_bounds(fwd_row, piece.col):
        return []
    target = state.board[fwd_row][piece.col]
    if (
        target is not None
        and target.piece_type in SAFETYBALL_TYPES
        and target.team == piece.team
        and target.stored_piece is None
        and piece.current_hp < piece.max_hp
        and piece.piece_type != PieceType.PIKACHU
        and len(state.all_pieces(piece.team)) >= 3
    ):
        return [Move(piece.row, piece.col, ActionType.MOVE, fwd_row, piece.col)]
    return []


def _squirtle_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _ROOK_DIRS)
    moves = (
        [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
        + [Move(piece.row, piece.col, ActionType.ATTACK, r, c) for r, c in enemies]
        + _forward_healball_entry(piece, state)
        + _trade_moves(piece, state)
    )
    return _expand_overflow_moves(piece, state, moves)


def _charmander_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    moves = []
    for dr, dc in _KNIGHT_JUMPS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    moves += _forward_healball_entry(piece, state)
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


def _bulbasaur_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _BISHOP_DIRS)
    moves = (
        [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
        + [Move(piece.row, piece.col, ActionType.ATTACK, r, c) for r, c in enemies]
        + _forward_healball_entry(piece, state)
        + _trade_moves(piece, state)
    )
    return _expand_overflow_moves(piece, state, moves)


def _mew_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _QUEEN_DIRS)
    moves = [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
    for r, c in enemies:
        for slot in _MEW_SLOTS:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c, move_slot=slot))
    if not state.foresight_used_last_turn[piece.team]:
        for r, c in empties + enemies:
            moves.append(Move(piece.row, piece.col, ActionType.FORESIGHT, r, c))
    moves += _forward_healball_entry(piece, state)
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


def _add_steps(
    piece: 'Piece',
    state: 'GameState',
    moves: list,
    dr: int,
    dc: int,
    max_steps: int,
) -> None:
    """
    Append MOVE/ATTACK moves along one direction for up to max_steps squares.
    Stops at the board edge, a friendly piece (blocked), or after attacking an enemy.
    """
    r, c = piece.row + dr, piece.col + dc
    for _ in range(max_steps):
        if not _in_bounds(r, c):
            break
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team:
            # Enemy Safetyballs block but cannot be attacked
            if occupant.piece_type not in SAFETYBALL_TYPES:
                moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
            break
        else:
            break  # friendly blocks
        r += dr
        c += dc


_STEALBALL_CANNOT_TARGET: frozenset = frozenset({PieceType.PIKACHU}) | PAWN_TYPES

def _pawn_filter(moves: list[Move], state: 'GameState') -> list[Move]:
    """Remove ATTACK moves whose target is an enemy pawn or Pikachu (immune to stealballs)."""
    return [
        m for m in moves
        if not (
            m.action_type == ActionType.ATTACK
            and state.board[m.target_row][m.target_col] is not None
            and state.board[m.target_row][m.target_col].piece_type in _STEALBALL_CANNOT_TARGET
        )
    ]


def _pokeball_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """
    Pokeball movement:
      - Up to 2 squares forward (own direction)
      - Up to 2 squares horizontal (left or right)
      - 1 square forward-diagonal (left and right)
    Pokeballs cannot target enemy pawns (pokeball/masterball) for capture.
    """
    moves: list[Move] = []
    fwd = _forward(piece.team)
    _add_steps(piece, state, moves, fwd,  0, 2)
    _add_steps(piece, state, moves,   0,  1, 2)
    _add_steps(piece, state, moves,   0, -1, 2)
    _add_steps(piece, state, moves, fwd,  1, 1)
    _add_steps(piece, state, moves, fwd, -1, 1)
    return _pawn_filter(moves, state)


def _masterball_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """
    Masterball = Pokeball + backward movement.
    Masterballs cannot target enemy pawns (pokeball/masterball) for capture.
    """
    moves: list[Move] = []
    fwd = _forward(piece.team)
    _add_steps(piece, state, moves,  fwd,  0, 2)
    _add_steps(piece, state, moves,    0,  1, 2)
    _add_steps(piece, state, moves,    0, -1, 2)
    _add_steps(piece, state, moves,  fwd,  1, 1)
    _add_steps(piece, state, moves,  fwd, -1, 1)
    _add_steps(piece, state, moves, -fwd,  0, 2)
    _add_steps(piece, state, moves, -fwd,  1, 1)
    _add_steps(piece, state, moves, -fwd, -1, 1)
    return _pawn_filter(moves, state)


# --- king and evolution generators ---

# All 8 adjacent squares (king movement range)
_KING_DIRS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]

# Eevee's held item → move_slot index used in the EVOLVE move
#   0=Vaporeon, 1=Flareon, 2=Leafeon, 3=Jolteon, 4=Espeon
_EEVEE_EVOLUTION_SLOT: dict[Item, int] = {
    Item.WATERSTONE:   0,
    Item.FIRESTONE:    1,
    Item.LEAFSTONE:    2,
    Item.THUNDERSTONE: 3,
    Item.BENTSPOON:    4,
}


def _king_standard_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """MOVE and ATTACK to all in-bounds adjacent squares."""
    moves = []
    for dr, dc in _KING_DIRS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    return moves


def _pikachu_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    moves = _king_standard_moves(piece, state)
    for dr, dc in _PIKACHU_EXTENDED_L:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    moves.append(Move(piece.row, piece.col, ActionType.EVOLVE, piece.row, piece.col))
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


_RAICHU_EXTRA_CARDINALS = [(2, 0), (-2, 0), (0, 2), (0, -2)]


def _raichu_extra_cardinals(piece: 'Piece', state: 'GameState', moves: list) -> None:
    """Add unobstructed 2-square cardinal jumps (leap over intermediate square)."""
    for dr, dc in _RAICHU_EXTRA_CARDINALS:
        dest_r, dest_c = piece.row + dr, piece.col + dc
        if not _in_bounds(dest_r, dest_c):
            continue
        dest = state.board[dest_r][dest_c]
        if dest is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, dest_r, dest_c))
        elif dest.team != piece.team and dest.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, dest_r, dest_c))


def _raichu_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Raichu: Pikachu pattern (king + L-jumps) plus 2-square cardinal slides."""
    moves = _king_standard_moves(piece, state)
    for dr, dc in _PIKACHU_EXTENDED_L:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    _raichu_extra_cardinals(piece, state, moves)
    moves += _forward_healball_entry(piece, state)
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


_QA_BASE_DAMAGE = 50


def _quick_attack_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """
    Quick Attack (attack-then-move): attack an adjacent enemy (king-range), then move
    king-range from the post-attack position. Used by Eevee and all eeveelutions except Espeon.
    target = attack target; secondary = movement destination after attack.
    If the attack KOs, the piece occupies the vacated square and moves from there.
    If no KO, the piece stays and moves from its original square.
    """
    moves = []
    for dr, dc in _KING_DIRS:
        att_r, att_c = piece.row + dr, piece.col + dc
        if not _in_bounds(att_r, att_c):
            continue
        target = state.board[att_r][att_c]
        if target is None or target.team == piece.team:
            continue
        if target.piece_type in SAFETYBALL_TYPES:
            continue

        type_mult = MATCHUP[piece.pokemon_type][target.pokemon_type]
        damage = max(10, round(_QA_BASE_DAMAGE * type_mult / 10) * 10)
        will_ko = damage >= target.current_hp

        post_r = att_r if will_ko else piece.row
        post_c = att_c if will_ko else piece.col

        for mdr, mdc in _KING_DIRS:
            dest_r, dest_c = post_r + mdr, post_c + mdc
            if not _in_bounds(dest_r, dest_c):
                continue
            occupant = state.board[dest_r][dest_c]
            # In the KO case, original square is vacated after the attack
            if will_ko and dest_r == piece.row and dest_c == piece.col:
                occupant = None
            if occupant is None:
                moves.append(Move(
                    piece.row, piece.col, ActionType.QUICK_ATTACK,
                    att_r, att_c,
                    secondary_row=dest_r, secondary_col=dest_c,
                ))
    return moves


def _add_safetyball_steps(
    piece: 'Piece',
    state: 'GameState',
    moves: list,
    dr: int,
    dc: int,
    max_steps: int,
) -> None:
    """
    Append Safetyball movement steps. Can move to empty squares or injured
    allied Pokémon (triggering storage). Stops at friendlies, enemies, and board edge.
    """
    r, c = piece.row + dr, piece.col + dc
    for _ in range(max_steps):
        if not _in_bounds(r, c):
            break
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team == piece.team:
            # Storable if: Safetyball is empty, ally is injured (has HP), not Pikachu,
            # and storing would leave at least one other piece on the board.
            if (
                piece.stored_piece is None
                and occupant.max_hp > 0
                and occupant.current_hp < occupant.max_hp
                and occupant.piece_type != PieceType.PIKACHU
                and len(state.all_pieces(piece.team)) >= 3
            ):
                moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
            break  # friendly always stops the ray
        else:
            break  # enemy stops the ray
        r += dr
        c += dc


def _safetyball_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Safetyball: defensive pawn — stores and heals allied Pokémon."""
    moves: list[Move] = []
    fwd = _forward(piece.team)
    if piece.stored_piece is not None:
        moves.append(Move(piece.row, piece.col, ActionType.RELEASE, piece.row, piece.col))
    _add_safetyball_steps(piece, state, moves, fwd,  0, 2)
    _add_safetyball_steps(piece, state, moves,   0,  1, 2)
    _add_safetyball_steps(piece, state, moves,   0, -1, 2)
    _add_safetyball_steps(piece, state, moves, fwd,  1, 1)
    _add_safetyball_steps(piece, state, moves, fwd, -1, 1)
    return moves


def _master_safetyball_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Master Safetyball: promoted Safetyball with omnidirectional movement."""
    moves: list[Move] = []
    fwd = _forward(piece.team)
    if piece.stored_piece is not None:
        moves.append(Move(piece.row, piece.col, ActionType.RELEASE, piece.row, piece.col))
    _add_safetyball_steps(piece, state, moves,  fwd,  0, 2)
    _add_safetyball_steps(piece, state, moves,    0,  1, 2)
    _add_safetyball_steps(piece, state, moves,    0, -1, 2)
    _add_safetyball_steps(piece, state, moves,  fwd,  1, 1)
    _add_safetyball_steps(piece, state, moves,  fwd, -1, 1)
    _add_safetyball_steps(piece, state, moves, -fwd,  0, 2)
    _add_safetyball_steps(piece, state, moves, -fwd,  1, 1)
    _add_safetyball_steps(piece, state, moves, -fwd, -1, 1)
    return moves


def _eevee_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    moves = _king_standard_moves(piece, state)
    moves += _quick_attack_moves(piece, state)
    slot = _EEVEE_EVOLUTION_SLOT.get(piece.held_item)
    if slot is not None:
        moves.append(Move(
            piece.row, piece.col, ActionType.EVOLVE,
            piece.row, piece.col, move_slot=slot,
        ))
    moves += _forward_healball_entry(piece, state)
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


def _vaporeon_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Vaporeon: king + rook sliding + Quick Attack (retained)."""
    empties, enemies = _sliding_squares(piece, state, _ROOK_DIRS)
    moves = _king_standard_moves(piece, state)
    king_targets = {(m.target_row, m.target_col) for m in moves}
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in king_targets]
    moves += [Move(piece.row, piece.col, ActionType.ATTACK, r, c)
              for r, c in enemies if (r, c) not in king_targets]
    moves += _quick_attack_moves(piece, state)
    moves += _forward_healball_entry(piece, state)
    return _expand_overflow_moves(piece, state, moves + _trade_moves(piece, state))


def _flareon_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Flareon: king + knight jumps (Flare Blitz ATTACK) + Quick Attack (retained)."""
    moves = _king_standard_moves(piece, state)
    for dr, dc in _KNIGHT_JUMPS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    moves += _quick_attack_moves(piece, state)
    moves += _forward_healball_entry(piece, state)
    return _expand_overflow_moves(piece, state, moves + _trade_moves(piece, state))


def _leafeon_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Leafeon: king + bishop sliding + Quick Attack (retained)."""
    empties, enemies = _sliding_squares(piece, state, _BISHOP_DIRS)
    moves = _king_standard_moves(piece, state)
    king_targets = {(m.target_row, m.target_col) for m in moves}
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in king_targets]
    moves += [Move(piece.row, piece.col, ActionType.ATTACK, r, c)
              for r, c in enemies if (r, c) not in king_targets]
    moves += _quick_attack_moves(piece, state)
    moves += _forward_healball_entry(piece, state)
    return _expand_overflow_moves(piece, state, moves + _trade_moves(piece, state))


def _jolteon_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Jolteon: king + L-jumps + unobstructed 2-sq cardinal jumps + 2-sq diagonal jumps + QA."""
    moves = _king_standard_moves(piece, state)
    for dr, dc in _PIKACHU_EXTENDED_L:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    _raichu_extra_cardinals(piece, state, moves)
    for dr, dc in _JOLTEON_DIAG_JUMPS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        dest = state.board[r][c]
        if dest is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif dest.team != piece.team and dest.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    moves += _quick_attack_moves(piece, state)
    moves += _forward_healball_entry(piece, state)
    return _expand_overflow_moves(piece, state, moves + _trade_moves(piece, state))


def _espeon_moves(piece: 'Piece', state: 'GameState') -> list[Move]:
    """Espeon: queen MOVE only (no ATTACK) + Foresight + Psywave. No Quick Attack."""
    empties, enemies = _sliding_squares(piece, state, _QUEEN_DIRS)
    adj_moves = [m for m in _king_standard_moves(piece, state)
                 if m.action_type == ActionType.MOVE]
    adj_targets = {(m.target_row, m.target_col) for m in adj_moves}
    moves = adj_moves
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in adj_targets]
    if not state.foresight_used_last_turn[piece.team]:
        for r, c in empties + enemies:
            moves.append(Move(piece.row, piece.col, ActionType.FORESIGHT, r, c))
    moves.append(Move(piece.row, piece.col, ActionType.PSYWAVE, piece.row, piece.col))
    moves += _forward_healball_entry(piece, state)
    moves += _trade_moves(piece, state)
    return _expand_overflow_moves(piece, state, moves)


# Dispatch table (all piece types now covered).
_PIECE_MOVE_FN = {
    PieceType.SQUIRTLE:          _squirtle_moves,
    PieceType.CHARMANDER:        _charmander_moves,
    PieceType.BULBASAUR:         _bulbasaur_moves,
    PieceType.MEW:               _mew_moves,
    PieceType.POKEBALL:          _pokeball_moves,
    PieceType.MASTERBALL:        _masterball_moves,
    PieceType.SAFETYBALL:        _safetyball_moves,
    PieceType.MASTER_SAFETYBALL: _master_safetyball_moves,
    PieceType.PIKACHU:           _pikachu_moves,
    PieceType.RAICHU:            _raichu_moves,
    PieceType.EEVEE:             _eevee_moves,
    PieceType.VAPOREON:          _vaporeon_moves,
    PieceType.FLAREON:           _flareon_moves,
    PieceType.LEAFEON:           _leafeon_moves,
    PieceType.JOLTEON:           _jolteon_moves,
    PieceType.ESPEON:            _espeon_moves,
}


def get_legal_moves(state: 'GameState') -> list[Move]:
    """Return all legal moves for the active player."""
    moves = []
    for piece in state.all_pieces(state.active_player):
        fn = _PIECE_MOVE_FN.get(piece.piece_type)
        if fn is not None:
            moves.extend(fn(piece, state))
    return moves
