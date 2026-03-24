"""
Core data structures for PokeChess game state.

Board is 8x8. Red (Pikachu) moves first — equivalent to White in chess.
Blue (Eevee) moves second — equivalent to Black.
Starting layout mirrors standard chess (rows 1,2 for Red, rows 7,8 for Blue).
"""

from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Team(Enum):
    RED = auto()   # Pikachu side, moves first
    BLUE = auto()  # Eevee side, moves second


class PieceType(Enum):
    # Standard pieces
    SQUIRTLE  = auto()  # Rook — Water, 200HP, Hydro Pump 100
    CHARMANDER = auto() # Knight — Fire, 200HP, Fire Blast 100
    BULBASAUR = auto()  # Bishop — Grass, 200HP, Solar Beam 100
    MEW       = auto()  # Queen — Psychic, 250HP, 4 moves
    # Pawns
    POKEBALL  = auto()  # Pawn — no type, stochastic capture
    MASTERBALL = auto() # Promoted pawn — 100% capture rate
    # Red King line
    PIKACHU   = auto()  # Red King — Electric, 200HP, Thunderbolt 100
    RAICHU    = auto()  # Evolved Red King — Electric, 250HP, Thunderbolt 100
    # Blue King line
    EEVEE     = auto()  # Blue King — Normal, 120HP, Quick Attack 50
    VAPOREON  = auto()  # Eevee evo — Water, 220HP, Hydro Pump 100
    FLAREON   = auto()  # Eevee evo — Fire, 220HP, Fire Blast 100
    LEAFEON   = auto()  # Eevee evo — Grass, 220HP, Solar Beam 100
    JOLTEON   = auto()  # Eevee evo — Electric, 220HP, Thunderbolt 100
    ESPEON    = auto()  # Eevee evo — Psychic, 220HP, Foresight 120


class Item(Enum):
    NONE        = auto()
    WATERSTONE  = auto()  # Held by Squirtle; enables Vaporeon evolution
    FIRESTONE   = auto()  # Held by Charmander; enables Flareon evolution
    LEAFSTONE   = auto()  # Held by Bulbasaur; enables Leafeon evolution
    THUNDERSTONE = auto() # Held by Pikachu; enables Raichu/Jolteon evolution
    BENTSPOON   = auto()  # Held by Mew; enables Espeon evolution


class PokemonType(Enum):
    WATER    = auto()
    FIRE     = auto()
    GRASS    = auto()
    PSYCHIC  = auto()
    ELECTRIC = auto()
    NORMAL   = auto()
    NONE     = auto()  # Pokeball/Masterball


# Type effectiveness: MATCHUP[attacker_type][defender_type] -> multiplier
# 2.0 = super effective, 1.0 = normal, 0.5 = not very effective
# NONE (Pokeball/Masterball) never uses this table — guard in rules.py before lookup.
MATCHUP: dict[PokemonType, dict[PokemonType, float]] = {
    PokemonType.WATER:    {PokemonType.WATER: 0.5, PokemonType.FIRE: 2.0,  PokemonType.GRASS: 0.5, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.FIRE:     {PokemonType.WATER: 0.5, PokemonType.FIRE: 0.5,  PokemonType.GRASS: 2.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.GRASS:    {PokemonType.WATER: 2.0, PokemonType.FIRE: 0.5,  PokemonType.GRASS: 0.5, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.PSYCHIC:  {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.ELECTRIC: {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.NORMAL:   {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.NONE:     {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
}

# Per-piece base stats
PIECE_TYPE: dict[PieceType, PokemonType] = {
    PieceType.SQUIRTLE:   PokemonType.WATER,
    PieceType.CHARMANDER: PokemonType.FIRE,
    PieceType.BULBASAUR:  PokemonType.GRASS,
    PieceType.MEW:        PokemonType.PSYCHIC,
    PieceType.POKEBALL:   PokemonType.NONE,
    PieceType.MASTERBALL: PokemonType.NONE,
    PieceType.PIKACHU:    PokemonType.ELECTRIC,
    PieceType.RAICHU:     PokemonType.ELECTRIC,
    PieceType.EEVEE:      PokemonType.NORMAL,
    PieceType.VAPOREON:   PokemonType.WATER,
    PieceType.FLAREON:    PokemonType.FIRE,
    PieceType.LEAFEON:    PokemonType.GRASS,
    PieceType.JOLTEON:    PokemonType.ELECTRIC,
    PieceType.ESPEON:     PokemonType.PSYCHIC,
}

MAX_HP: dict[PieceType, int] = {
    PieceType.SQUIRTLE:   200,
    PieceType.CHARMANDER: 200,
    PieceType.BULBASAUR:  200,
    PieceType.MEW:        250,
    PieceType.POKEBALL:   0,    # No HP — capture-only
    PieceType.MASTERBALL: 0,
    PieceType.PIKACHU:    200,
    PieceType.RAICHU:     250,
    PieceType.EEVEE:      120,
    PieceType.VAPOREON:   220,
    PieceType.FLAREON:    220,
    PieceType.LEAFEON:    220,
    PieceType.JOLTEON:    220,
    PieceType.ESPEON:     220,
}

DEFAULT_HELD_ITEM: dict[PieceType, Item] = {
    PieceType.SQUIRTLE:   Item.WATERSTONE,
    PieceType.CHARMANDER: Item.FIRESTONE,
    PieceType.BULBASAUR:  Item.LEAFSTONE,
    PieceType.MEW:        Item.BENTSPOON,
    PieceType.POKEBALL:   Item.NONE,
    PieceType.MASTERBALL: Item.NONE,
    PieceType.PIKACHU:    Item.THUNDERSTONE,
    PieceType.RAICHU:     Item.NONE,
    PieceType.EEVEE:      Item.NONE,       # Eevee starts with no stone
    PieceType.VAPOREON:   Item.NONE,
    PieceType.FLAREON:    Item.NONE,
    PieceType.LEAFEON:    Item.NONE,
    PieceType.JOLTEON:    Item.NONE,
    PieceType.ESPEON:     Item.NONE,
}


@dataclass
class Piece:
    piece_type: PieceType
    team: Team
    row: int
    col: int
    current_hp: int
    held_item: Item

    @classmethod
    def create(cls, piece_type: PieceType, team: Team, row: int, col: int) -> Piece:
        return cls(
            piece_type=piece_type,
            team=team,
            row=row,
            col=col,
            current_hp=MAX_HP[piece_type],
            held_item=DEFAULT_HELD_ITEM[piece_type],
        )

    @property
    def max_hp(self) -> int:
        return MAX_HP[self.piece_type]

    @property
    def pokemon_type(self) -> PokemonType:
        return PIECE_TYPE[self.piece_type]

    @property
    def is_king(self) -> bool:
        return self.piece_type in (
            PieceType.PIKACHU, PieceType.RAICHU,
            PieceType.EEVEE, PieceType.VAPOREON, PieceType.FLAREON,
            PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
        )

    @property
    def is_pawn(self) -> bool:
        return self.piece_type in (PieceType.POKEBALL, PieceType.MASTERBALL)

    def copy(self) -> Piece:
        return Piece(
            piece_type=self.piece_type,
            team=self.team,
            row=self.row,
            col=self.col,
            current_hp=self.current_hp,
            held_item=self.held_item,
        )


@dataclass
class ForesightEffect:
    """A pending Foresight attack that resolves at the start of the caster's next turn."""
    target_row: int
    target_col: int
    damage: int
    resolves_on_turn: int   # Turn number on which this fires


@dataclass
class GameState:
    """
    Full game state. Designed to be efficiently copyable for MCTS simulations.

    board[row][col] = Piece or None. Row 0 is Red's back rank, row 7 is Blue's.
    """
    board: list[list[Optional[Piece]]]
    active_player: Team
    turn_number: int
    # Per-team pending Foresight: both sides can have one queued simultaneously
    # (e.g. Red's Mew and Blue's Espeon each use Foresight on consecutive turns).
    pending_foresight: dict[Team, Optional[ForesightEffect]]

    # Track whether Mew/Espeon used Foresight last turn (can't use consecutively)
    foresight_used_last_turn: dict[Team, bool] = field(default_factory=lambda: {Team.RED: False, Team.BLUE: False})

    @classmethod
    def new_game(cls) -> GameState:
        """Set up the standard starting position."""
        board: list[list[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
        _place_starting_pieces(board)
        return cls(
            board=board,
            active_player=Team.RED,
            turn_number=1,
            pending_foresight={Team.RED: None, Team.BLUE: None},
        )

    def piece_at(self, row: int, col: int) -> Optional[Piece]:
        return self.board[row][col]

    def all_pieces(self, team: Optional[Team] = None) -> list[Piece]:
        pieces = [p for row in self.board for p in row if p is not None]
        if team is not None:
            pieces = [p for p in pieces if p.team == team]
        return pieces

    def copy(self) -> GameState:
        new_board = [[p.copy() if p is not None else None for p in row] for row in self.board]
        return GameState(
            board=new_board,
            active_player=self.active_player,
            turn_number=self.turn_number,
            pending_foresight={
                team: dataclasses.replace(fx) if fx is not None else None
                for team, fx in self.pending_foresight.items()
            },
            foresight_used_last_turn=dict(self.foresight_used_last_turn),
        )


def _place_starting_pieces(board: list[list[Optional[Piece]]]) -> None:
    """
    Standard chess starting layout.
    Red (Pikachu) occupies rows 0-1, Blue (Eevee) occupies rows 6-7.
    Back rank order (col 0-7): Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook
    """
    back_rank = [
        PieceType.SQUIRTLE,
        PieceType.CHARMANDER,
        PieceType.BULBASAUR,
        PieceType.MEW,
        None,  # King placed separately (Pikachu/Eevee)
        PieceType.BULBASAUR,
        PieceType.CHARMANDER,
        PieceType.SQUIRTLE,
    ]

    for col, pt in enumerate(back_rank):
        if pt is not None:
            board[0][col] = Piece.create(pt, Team.RED, 0, col)
            board[7][col] = Piece.create(pt, Team.BLUE, 7, col)

    board[0][4] = Piece.create(PieceType.PIKACHU, Team.RED, 0, 4)
    board[7][4] = Piece.create(PieceType.EEVEE, Team.BLUE, 7, 4)

    for col in range(8):
        board[1][col] = Piece.create(PieceType.POKEBALL, Team.RED, 1, col)
        board[6][col] = Piece.create(PieceType.POKEBALL, Team.BLUE, 6, col)
