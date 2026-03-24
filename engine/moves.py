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
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

from .state import PieceType, Team, Item

if TYPE_CHECKING:
    from .state import GameState, Piece


class ActionType(Enum):
    MOVE         = auto()  # Move to empty square
    ATTACK       = auto()  # Attack target in movement range
    FORESIGHT    = auto()  # Delayed attack (Mew/Espeon)
    TRADE        = auto()  # Swap held items with adjacent teammate
    EVOLVE       = auto()  # Trigger evolution (costs full turn)
    QUICK_ATTACK = auto()  # Eevee only: move + attack same turn


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


# --- movement geometry ---

_ROOK_DIRS    = [(0, 1), (0, -1), (1, 0), (-1, 0)]
_BISHOP_DIRS  = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_QUEEN_DIRS   = _ROOK_DIRS + _BISHOP_DIRS
_KNIGHT_JUMPS = [
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2),
]
_MEW_SLOTS = (0, 1, 2, 3)


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8


def _sliding_squares(
    piece: Piece,
    state: GameState,
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
                enemies.append((r, c))
                break
            else:
                break  # friendly blocks the ray
            r += dr
            c += dc
    return empties, enemies


def _trade_moves(piece: Piece, state: GameState) -> list[Move]:
    """
    TRADE with any adjacent (including diagonal) friendly piece that holds a different item.
    Both pieces swap their held_item; only makes sense when items differ.
    """
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
                and neighbor.held_item != piece.held_item
            ):
                moves.append(Move(piece.row, piece.col, ActionType.TRADE, r, c))
    return moves


# --- per-piece-type generators ---

def _squirtle_moves(piece: Piece, state: GameState) -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _ROOK_DIRS)
    return (
        [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
        + [Move(piece.row, piece.col, ActionType.ATTACK, r, c) for r, c in enemies]
        + _trade_moves(piece, state)
    )


def _charmander_moves(piece: Piece, state: GameState) -> list[Move]:
    moves = []
    for dr, dc in _KNIGHT_JUMPS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    moves += _trade_moves(piece, state)
    return moves


def _bulbasaur_moves(piece: Piece, state: GameState) -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _BISHOP_DIRS)
    return (
        [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
        + [Move(piece.row, piece.col, ActionType.ATTACK, r, c) for r, c in enemies]
        + _trade_moves(piece, state)
    )


def _mew_moves(piece: Piece, state: GameState) -> list[Move]:
    empties, enemies = _sliding_squares(piece, state, _QUEEN_DIRS)
    moves = [Move(piece.row, piece.col, ActionType.MOVE, r, c) for r, c in empties]
    # Mew selects one of 4 move slots per attack — different slots deal different damage
    for r, c in enemies:
        for slot in _MEW_SLOTS:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c, move_slot=slot))
    # Foresight targets any reachable square; cannot be used on consecutive turns
    if not state.foresight_used_last_turn[piece.team]:
        for r, c in empties + enemies:
            moves.append(Move(piece.row, piece.col, ActionType.FORESIGHT, r, c))
    moves += _trade_moves(piece, state)
    return moves


def _forward(team: Team) -> int:
    """Row delta for 'forward': +1 for RED (toward row 7), -1 for BLUE (toward row 0)."""
    return 1 if team == Team.RED else -1


def _add_steps(
    piece: Piece,
    state: GameState,
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
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
            break
        else:
            break  # friendly blocks
        r += dr
        c += dc


def _pokeball_moves(piece: Piece, state: GameState) -> list[Move]:
    """
    Pokeball movement:
      - Up to 2 squares forward (own direction)
      - Up to 2 squares horizontal (left or right)
      - 1 square forward-diagonal (left and right)
    All reachable squares can be moved to (if empty) or attacked (if enemy).
    """
    moves: list[Move] = []
    fwd = _forward(piece.team)
    _add_steps(piece, state, moves, fwd,  0, 2)   # forward
    _add_steps(piece, state, moves,   0,  1, 2)   # right
    _add_steps(piece, state, moves,   0, -1, 2)   # left
    _add_steps(piece, state, moves, fwd,  1, 1)   # forward-right diagonal
    _add_steps(piece, state, moves, fwd, -1, 1)   # forward-left diagonal
    return moves


def _masterball_moves(piece: Piece, state: GameState) -> list[Move]:
    """
    Masterball = Pokeball + backward movement:
      - Up to 2 squares backward
      - 1 square backward-diagonal (left and right)
    """
    moves: list[Move] = []
    fwd = _forward(piece.team)
    _add_steps(piece, state, moves,  fwd,  0, 2)  # forward
    _add_steps(piece, state, moves,    0,  1, 2)  # right
    _add_steps(piece, state, moves,    0, -1, 2)  # left
    _add_steps(piece, state, moves,  fwd,  1, 1)  # forward-right diagonal
    _add_steps(piece, state, moves,  fwd, -1, 1)  # forward-left diagonal
    _add_steps(piece, state, moves, -fwd,  0, 2)  # backward
    _add_steps(piece, state, moves, -fwd,  1, 1)  # backward-right diagonal
    _add_steps(piece, state, moves, -fwd, -1, 1)  # backward-left diagonal
    return moves


# --- king and evolution generators ---

# All 8 adjacent squares (king movement range)
_KING_DIRS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]

# Eevee's held item → move_slot index used in the EVOLVE move
# move_slot encodes the evolution choice so rules.py knows which PieceType to create.
#   0=Vaporeon, 1=Flareon, 2=Leafeon, 3=Jolteon, 4=Espeon
_EEVEE_EVOLUTION_SLOT: dict[Item, int] = {
    Item.WATERSTONE:   0,  # → Vaporeon
    Item.FIRESTONE:    1,  # → Flareon
    Item.LEAFSTONE:    2,  # → Leafeon
    Item.THUNDERSTONE: 3,  # → Jolteon
    Item.BENTSPOON:    4,  # → Espeon
}


def _king_standard_moves(piece: Piece, state: GameState) -> list[Move]:
    """MOVE and ATTACK to all in-bounds adjacent squares."""
    moves = []
    for dr, dc in _KING_DIRS:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    return moves


def _pikachu_moves(piece: Piece, state: GameState) -> list[Move]:
    moves = _king_standard_moves(piece, state)
    # Evolve to Raichu: costs a full turn; happens in place
    moves.append(Move(piece.row, piece.col, ActionType.EVOLVE, piece.row, piece.col))
    moves += _trade_moves(piece, state)
    return moves


def _raichu_moves(piece: Piece, state: GameState) -> list[Move]:
    return _king_standard_moves(piece, state) + _trade_moves(piece, state)


def _eevee_quick_attacks(piece: Piece, state: GameState) -> list[Move]:
    """
    Quick Attack: move to an empty adjacent square, then attack any enemy
    adjacent (king range) to that destination — all in one turn.
    target = movement destination; secondary = attack target from new position.
    """
    moves = []
    for dr, dc in _KING_DIRS:
        dest_r, dest_c = piece.row + dr, piece.col + dc
        if not _in_bounds(dest_r, dest_c) or state.board[dest_r][dest_c] is not None:
            continue  # destination must be empty
        for adr, adc in _KING_DIRS:
            att_r, att_c = dest_r + adr, dest_c + adc
            if not _in_bounds(att_r, att_c):
                continue
            occupant = state.board[att_r][att_c]
            if occupant is not None and occupant.team != piece.team:
                moves.append(Move(
                    piece.row, piece.col, ActionType.QUICK_ATTACK,
                    dest_r, dest_c,
                    secondary_row=att_r, secondary_col=att_c,
                ))
    return moves


def _eevee_moves(piece: Piece, state: GameState) -> list[Move]:
    moves = _king_standard_moves(piece, state)
    moves += _eevee_quick_attacks(piece, state)
    # Evolve if holding an evolution stone; move_slot encodes which evolution
    slot = _EEVEE_EVOLUTION_SLOT.get(piece.held_item)
    if slot is not None:
        moves.append(Move(
            piece.row, piece.col, ActionType.EVOLVE,
            piece.row, piece.col, move_slot=slot,
        ))
    moves += _trade_moves(piece, state)
    return moves


def _evolved_eevee_moves(piece: Piece, state: GameState) -> list[Move]:
    """Vaporeon / Flareon / Leafeon / Jolteon: standard king movement."""
    return _king_standard_moves(piece, state) + _trade_moves(piece, state)


def _espeon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Espeon: king movement + Foresight targeting any adjacent reachable square."""
    moves = _king_standard_moves(piece, state)
    if not state.foresight_used_last_turn[piece.team]:
        for dr, dc in _KING_DIRS:
            r, c = piece.row + dr, piece.col + dc
            if not _in_bounds(r, c):
                continue
            occupant = state.board[r][c]
            # Can foresight any adjacent square not occupied by a friendly
            if occupant is None or occupant.team != piece.team:
                moves.append(Move(piece.row, piece.col, ActionType.FORESIGHT, r, c))
    moves += _trade_moves(piece, state)
    return moves


# Dispatch table (all piece types now covered).
_PIECE_MOVE_FN = {
    PieceType.SQUIRTLE:   _squirtle_moves,
    PieceType.CHARMANDER: _charmander_moves,
    PieceType.BULBASAUR:  _bulbasaur_moves,
    PieceType.MEW:        _mew_moves,
    PieceType.POKEBALL:   _pokeball_moves,
    PieceType.MASTERBALL: _masterball_moves,
    PieceType.PIKACHU:    _pikachu_moves,
    PieceType.RAICHU:     _raichu_moves,
    PieceType.EEVEE:      _eevee_moves,
    PieceType.VAPOREON:   _evolved_eevee_moves,
    PieceType.FLAREON:    _evolved_eevee_moves,
    PieceType.LEAFEON:    _evolved_eevee_moves,
    PieceType.JOLTEON:    _evolved_eevee_moves,
    PieceType.ESPEON:     _espeon_moves,
}


def get_legal_moves(state: GameState) -> list[Move]:
    """Return all legal moves for the active player."""
    moves = []
    for piece in state.all_pieces(state.active_player):
        fn = _PIECE_MOVE_FN.get(piece.piece_type)
        if fn is not None:
            moves.extend(fn(piece, state))
    return moves
