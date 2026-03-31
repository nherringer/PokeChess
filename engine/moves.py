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

from .state import PieceType, Team, Item, PAWN_TYPES, SAFETYBALL_TYPES, MATCHUP, PokemonType

if TYPE_CHECKING:
    from .state import GameState, Piece


class ActionType(Enum):
    MOVE         = auto()  # Move to empty square (or Safetyball onto injured ally)
    ATTACK       = auto()  # Attack target in movement range
    FORESIGHT    = auto()  # Delayed attack (Mew/Espeon)
    TRADE        = auto()  # Swap held items with adjacent teammate
    EVOLVE       = auto()  # Trigger evolution (costs full turn)
    QUICK_ATTACK = auto()  # Eevee only: attack then move same turn
    RELEASE      = auto()  # Safetyball: release stored Pokémon in place


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
_PIKACHU_EXTENDED_L = [(3,1),(3,-1),(-3,1),(-3,-1),(1,3),(1,-3),(-1,3),(-1,-3)]
_MEW_SLOTS = (0, 1, 2)


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
                # Enemy Safetyballs block the ray but cannot be attacked
                if occupant.piece_type not in SAFETYBALL_TYPES:
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
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
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
            # Enemy Safetyballs block but cannot be attacked
            if occupant.piece_type not in SAFETYBALL_TYPES:
                moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
            break
        else:
            break  # friendly blocks
        r += dr
        c += dc


_STEALBALL_CANNOT_TARGET: frozenset = frozenset({PieceType.PIKACHU}) | PAWN_TYPES

def _pawn_filter(moves: list[Move], state: GameState) -> list[Move]:
    """Remove ATTACK moves whose target is an enemy pawn or Pikachu (immune to stealballs)."""
    return [
        m for m in moves
        if not (
            m.action_type == ActionType.ATTACK
            and state.board[m.target_row][m.target_col] is not None
            and state.board[m.target_row][m.target_col].piece_type in _STEALBALL_CANNOT_TARGET
        )
    ]


def _pokeball_moves(piece: Piece, state: GameState) -> list[Move]:
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


def _masterball_moves(piece: Piece, state: GameState) -> list[Move]:
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
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    return moves


def _pikachu_moves(piece: Piece, state: GameState) -> list[Move]:
    moves = _king_standard_moves(piece, state)
    # Extended L-shape jumps (3+1) — leaps over pieces
    for dr, dc in _PIKACHU_EXTENDED_L:
        r, c = piece.row + dr, piece.col + dc
        if not _in_bounds(r, c):
            continue
        occupant = state.board[r][c]
        if occupant is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, r, c))
        elif occupant.team != piece.team and occupant.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, r, c))
    # Evolve to Raichu: costs a full turn; happens in place
    moves.append(Move(piece.row, piece.col, ActionType.EVOLVE, piece.row, piece.col))
    moves += _trade_moves(piece, state)
    return moves


_RAICHU_EXTRA_CARDINALS = [(2, 0), (-2, 0), (0, 2), (0, -2)]


def _raichu_extra_cardinals(piece: 'Piece', state: 'GameState', moves: list) -> None:
    """Add 2-square cardinal slides (blocked if the intermediate square is occupied)."""
    for dr, dc in _RAICHU_EXTRA_CARDINALS:
        mid_r, mid_c  = piece.row + dr // 2, piece.col + dc // 2
        dest_r, dest_c = piece.row + dr,      piece.col + dc
        if not _in_bounds(dest_r, dest_c):
            continue
        if state.board[mid_r][mid_c] is not None:
            continue  # intermediate square occupied — slide blocked
        dest = state.board[dest_r][dest_c]
        if dest is None:
            moves.append(Move(piece.row, piece.col, ActionType.MOVE, dest_r, dest_c))
        elif dest.team != piece.team and dest.piece_type not in SAFETYBALL_TYPES:
            moves.append(Move(piece.row, piece.col, ActionType.ATTACK, dest_r, dest_c))


def _raichu_moves(piece: Piece, state: GameState) -> list[Move]:
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
    return moves + _trade_moves(piece, state)


def _eevee_quick_attacks(piece: Piece, state: GameState) -> list[Move]:
    """
    Quick Attack (attack-then-move): attack an adjacent enemy first, then move
    king-range from the post-attack position.
    target = attack target; secondary = movement destination after attack.
    If the attack KOs, Eevee occupies the vacated square and moves from there.
    If no KO, Eevee stays and moves from its original square.
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

        # Determine if attack KOs (Eevee is NORMAL type, base damage 50)
        type_mult = MATCHUP[PokemonType.NORMAL][target.pokemon_type]
        damage = max(10, round(50 * type_mult / 10) * 10)
        will_ko = damage >= target.current_hp

        # Post-attack position: target square (if KO) or original square (if no KO)
        post_r = att_r if will_ko else piece.row
        post_c = att_c if will_ko else piece.col

        for mdr, mdc in _KING_DIRS:
            dest_r, dest_c = post_r + mdr, post_c + mdc
            if not _in_bounds(dest_r, dest_c):
                continue
            occupant = state.board[dest_r][dest_c]
            # In the KO case, Eevee's original square will be vacated after the attack
            if will_ko and dest_r == piece.row and dest_c == piece.col:
                occupant = None  # treat as empty (Eevee will have left)
            if occupant is None:
                moves.append(Move(
                    piece.row, piece.col, ActionType.QUICK_ATTACK,
                    att_r, att_c,
                    secondary_row=dest_r, secondary_col=dest_c,
                ))
    return moves


def _add_safetyball_steps(
    piece: Piece,
    state: GameState,
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


def _safetyball_moves(piece: Piece, state: GameState) -> list[Move]:
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


def _master_safetyball_moves(piece: Piece, state: GameState) -> list[Move]:
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


def _vaporeon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Vaporeon: king + rook sliding."""
    empties, enemies = _sliding_squares(piece, state, _ROOK_DIRS)
    moves = _king_standard_moves(piece, state)
    king_targets = {(m.target_row, m.target_col) for m in moves}
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in king_targets]
    moves += [Move(piece.row, piece.col, ActionType.ATTACK, r, c)
              for r, c in enemies if (r, c) not in king_targets]
    return moves + _trade_moves(piece, state)


def _flareon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Flareon: king + knight jumps (mirrors Charmander, the fire knight)."""
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
    return moves + _trade_moves(piece, state)


def _leafeon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Leafeon: king + bishop sliding."""
    empties, enemies = _sliding_squares(piece, state, _BISHOP_DIRS)
    moves = _king_standard_moves(piece, state)
    king_targets = {(m.target_row, m.target_col) for m in moves}
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in king_targets]
    moves += [Move(piece.row, piece.col, ActionType.ATTACK, r, c)
              for r, c in enemies if (r, c) not in king_targets]
    return moves + _trade_moves(piece, state)


def _jolteon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Jolteon: identical pattern to Raichu — king + L-jumps + 2-square cardinal slides."""
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
    return moves + _trade_moves(piece, state)


def _espeon_moves(piece: Piece, state: GameState) -> list[Move]:
    """Espeon: queen movement (king + full sliding) + Foresight on all reachable squares."""
    empties, enemies = _sliding_squares(piece, state, _QUEEN_DIRS)
    moves = _king_standard_moves(piece, state)
    king_targets = {(m.target_row, m.target_col) for m in moves}
    moves += [Move(piece.row, piece.col, ActionType.MOVE, r, c)
              for r, c in empties if (r, c) not in king_targets]
    moves += [Move(piece.row, piece.col, ActionType.ATTACK, r, c)
              for r, c in enemies if (r, c) not in king_targets]
    if not state.foresight_used_last_turn[piece.team]:
        # Foresight can target any queen-range reachable square (like Mew)
        for r, c in empties + enemies:
            moves.append(Move(piece.row, piece.col, ActionType.FORESIGHT, r, c))
    return moves + _trade_moves(piece, state)


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


def get_legal_moves(state: GameState) -> list[Move]:
    """Return all legal moves for the active player."""
    moves = []
    for piece in state.all_pieces(state.active_player):
        fn = _PIECE_MOVE_FN.get(piece.piece_type)
        if fn is not None:
            moves.extend(fn(piece, state))
    return moves
