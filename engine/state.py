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
from typing import NamedTuple, Optional


class Team(Enum):
    RED = auto()   # moves first
    BLUE = auto()


class PieceType(Enum):
    SQUIRTLE         = auto()  # Rook
    CHARMANDER       = auto()  # Knight
    BULBASAUR        = auto()  # Bishop
    MEW              = auto()  # Queen
    POKEBALL         = auto()  # Stealball (offensive pawn)
    MASTERBALL       = auto()  # Master Stealball (promoted Stealball)
    SAFETYBALL       = auto()  # Defensive pawn — stores/heals allies
    MASTER_SAFETYBALL = auto() # Promoted Safetyball
    PIKACHU          = auto()
    RAICHU           = auto()
    EEVEE            = auto()
    VAPOREON         = auto()
    FLAREON          = auto()
    LEAFEON          = auto()
    JOLTEON          = auto()
    ESPEON           = auto()


class Item(Enum):
    NONE         = auto()
    WATERSTONE   = auto()
    FIRESTONE    = auto()
    LEAFSTONE    = auto()
    THUNDERSTONE = auto()
    BENTSPOON    = auto()


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
    PokemonType.ELECTRIC: {PokemonType.WATER: 2.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.NORMAL:   {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
    PokemonType.NONE:     {PokemonType.WATER: 1.0, PokemonType.FIRE: 1.0,  PokemonType.GRASS: 1.0, PokemonType.PSYCHIC: 1.0, PokemonType.ELECTRIC: 1.0, PokemonType.NORMAL: 1.0, PokemonType.NONE: 1.0},
}


class PieceStats(NamedTuple):
    pokemon_type: PokemonType
    max_hp: int
    default_item: Item


# Single source of truth for all per-type constants.
PIECE_STATS: dict[PieceType, PieceStats] = {
    PieceType.SQUIRTLE:          PieceStats(PokemonType.WATER,    200, Item.WATERSTONE),
    PieceType.CHARMANDER:        PieceStats(PokemonType.FIRE,     200, Item.FIRESTONE),
    PieceType.BULBASAUR:         PieceStats(PokemonType.GRASS,    200, Item.LEAFSTONE),
    PieceType.MEW:               PieceStats(PokemonType.PSYCHIC,  250, Item.BENTSPOON),
    PieceType.POKEBALL:          PieceStats(PokemonType.NONE,     0,   Item.NONE),
    PieceType.MASTERBALL:        PieceStats(PokemonType.NONE,     0,   Item.NONE),
    PieceType.SAFETYBALL:        PieceStats(PokemonType.NONE,     0,   Item.NONE),
    PieceType.MASTER_SAFETYBALL: PieceStats(PokemonType.NONE,     0,   Item.NONE),
    PieceType.PIKACHU:           PieceStats(PokemonType.ELECTRIC, 200, Item.THUNDERSTONE),
    PieceType.RAICHU:            PieceStats(PokemonType.ELECTRIC, 250, Item.NONE),
    PieceType.EEVEE:             PieceStats(PokemonType.NORMAL,   120, Item.NONE),
    PieceType.VAPOREON:          PieceStats(PokemonType.WATER,    220, Item.NONE),
    PieceType.FLAREON:           PieceStats(PokemonType.FIRE,     220, Item.NONE),
    PieceType.LEAFEON:           PieceStats(PokemonType.GRASS,    220, Item.NONE),
    PieceType.JOLTEON:           PieceStats(PokemonType.ELECTRIC, 220, Item.NONE),
    PieceType.ESPEON:            PieceStats(PokemonType.PSYCHIC,  220, Item.NONE),
}

# Authoritative sets used by Piece.is_king and Piece.is_pawn.
KING_TYPES: frozenset[PieceType] = frozenset({
    PieceType.PIKACHU, PieceType.RAICHU,
    PieceType.EEVEE, PieceType.VAPOREON, PieceType.FLAREON,
    PieceType.LEAFEON, PieceType.JOLTEON, PieceType.ESPEON,
})
PAWN_TYPES: frozenset[PieceType] = frozenset({
    PieceType.POKEBALL, PieceType.MASTERBALL,
    PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL,
})
# Safetyballs cannot be attacked or captured by any piece.
SAFETYBALL_TYPES: frozenset[PieceType] = frozenset({
    PieceType.SAFETYBALL, PieceType.MASTER_SAFETYBALL,
})


@dataclass
class Piece:
    piece_type: PieceType
    team: Team
    row: int
    col: int
    current_hp: int
    held_item: Item
    # Safetyball only: the Pokémon currently stored inside (None if empty).
    stored_piece: Optional['Piece'] = None
    # Stable UUID string assigned by the app layer; None for pieces that don't
    # have a persistent identity (bot-side copies, rollout simulations, etc.).
    # The engine never generates or validates this field — it's purely a carrier.
    id: Optional[str] = None

    @classmethod
    def create(cls, piece_type: PieceType, team: Team, row: int, col: int) -> Piece:
        stats = PIECE_STATS[piece_type]
        return cls(
            piece_type=piece_type,
            team=team,
            row=row,
            col=col,
            current_hp=stats.max_hp,
            held_item=stats.default_item,
        )

    @property
    def max_hp(self) -> int:
        return PIECE_STATS[self.piece_type].max_hp

    @property
    def pokemon_type(self) -> PokemonType:
        return PIECE_STATS[self.piece_type].pokemon_type

    @property
    def is_king(self) -> bool:
        return self.piece_type in KING_TYPES

    @property
    def is_pawn(self) -> bool:
        return self.piece_type in PAWN_TYPES

    def copy(self) -> Piece:
        c = dataclasses.replace(self)
        if self.stored_piece is not None:
            c.stored_piece = self.stored_piece.copy()
        return c


@dataclass
class ForesightEffect:
    """A pending Foresight attack that resolves at the start of the caster's next turn."""
    target_row: int
    target_col: int
    damage: int
    resolves_on_turn: int
    # Position of the piece that cast Foresight, stored so history attribution
    # is unambiguous when both MEW and ESPEON exist on the same team.
    # -1 means unknown (e.g. deserialized from an old save without this field).
    caster_row: int = -1
    caster_col: int = -1


@dataclass
class GameState:
    """
    Full game state. Designed to be efficiently copyable for MCTS simulations.

    board[row][col] = Piece or None. Row 0 is Red's back rank, row 7 is Blue's.
    """
    board: list[list[Optional[Piece]]]
    active_player: Team
    turn_number: int
    # Per-team: both sides can have a Foresight queued simultaneously
    # (Red's Mew and Blue's Espeon can each use it on back-to-back turns).
    pending_foresight: dict[Team, Optional[ForesightEffect]]
    # Foresight cannot be used on consecutive turns by the same team.
    # Stored explicitly because pending_foresight is cleared at resolution,
    # before the same team's next move decision.
    foresight_used_last_turn: dict[Team, bool] = field(
        default_factory=lambda: {Team.RED: False, Team.BLUE: False}
    )
    has_traded: dict[Team, bool] = field(
        default_factory=lambda: {Team.RED: False, Team.BLUE: False}
    )

    @classmethod
    def from_dict(cls, d: dict) -> GameState:
        """
        Deserialize a GameState from the wire-format dict produced by
        app/game_logic/serialization.py's state_to_dict().

        Extra keys on piece dicts (e.g. "id") are silently ignored.
        """
        board: list[list[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
        for pd in d["board"]:
            piece = _piece_from_dict(pd)
            board[piece.row][piece.col] = piece

        return cls(
            board=board,
            active_player=Team[d["active_player"]],
            turn_number=d["turn_number"],
            pending_foresight={
                Team.RED: _foresight_from_dict(d["pending_foresight"]["RED"]),
                Team.BLUE: _foresight_from_dict(d["pending_foresight"]["BLUE"]),
            },
            foresight_used_last_turn={
                Team.RED: d["foresight_used_last_turn"]["RED"],
                Team.BLUE: d["foresight_used_last_turn"]["BLUE"],
            },
            has_traded={
                Team.RED: d["has_traded"]["RED"],
                Team.BLUE: d["has_traded"]["BLUE"],
            },
        )

    @classmethod
    def new_game(cls) -> GameState:
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
        return [
            p
            for row in self.board
            for p in row
            if p is not None and (team is None or p.team == team)
        ]

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
            has_traded=dict(self.has_traded),
        )


def _piece_from_dict(d: dict) -> Piece:
    """Deserialize a Piece from a wire-format dict. Extra keys (e.g. 'id') are ignored."""
    piece = Piece(
        piece_type=PieceType[d["piece_type"]],
        team=Team[d["team"]],
        row=d["row"],
        col=d["col"],
        current_hp=d["current_hp"],
        held_item=Item[d["held_item"]],
        id=d.get("id"),
    )
    if d.get("stored_piece") is not None:
        piece.stored_piece = _piece_from_dict(d["stored_piece"])
    return piece


def _foresight_from_dict(d: Optional[dict]) -> Optional[ForesightEffect]:
    """Deserialize a ForesightEffect from a wire-format dict, or return None."""
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

    # Pawn row: Safetyballs on middle 4 cols (2-5), Stealballs on outer 4 cols (0-1, 6-7)
    for col in range(8):
        pawn_type = PieceType.SAFETYBALL if 2 <= col <= 5 else PieceType.POKEBALL
        board[1][col] = Piece.create(pawn_type, Team.RED, 1, col)
        board[6][col] = Piece.create(pawn_type, Team.BLUE, 6, col)
