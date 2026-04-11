"""Tests for app/game_logic: XP and id_map (no FastAPI)."""

from engine import GameState, Piece, PieceType, Team
from engine.moves import Move, ActionType
from engine.rules import apply_move

from app.game_logic.id_map import remap_ids
from app.game_logic.xp import compute_xp


def empty_state(active: Team = Team.RED, turn: int = 1) -> GameState:
    board = [[None] * 8 for _ in range(8)]
    return GameState(
        board=board,
        active_player=active,
        turn_number=turn,
        pending_foresight={Team.RED: None, Team.BLUE: None},
    )


def place(state: GameState, pt: PieceType, team: Team, row: int, col: int) -> Piece:
    piece = Piece.create(pt, team, row, col)
    state.board[row][col] = piece
    return piece


def make_move(pt: PieceType, pr: int, pc: int, at: ActionType, tr: int, tc: int, **kw) -> Move:
    return Move(
        piece_row=pr,
        piece_col=pc,
        action_type=at,
        target_row=tr,
        target_col=tc,
        **kw,
    )


class TestComputeXpForesight:
    def test_foresight_cast_does_not_double_count_with_resolve(self):
        caster = "11111111-1111-1111-1111-111111111111"
        history = [
            {
                "action_type": "foresight",
                "piece_id": caster,
                "result": {"damage": 120, "target_row": 5, "target_col": 5},
            },
            {
                "action_type": "foresight_resolve",
                "piece_id": caster,
                "result": {"damage": 120},
            },
        ]
        xp = compute_xp(history)
        assert xp.get(caster) == 120

    def test_attack_damage_still_counts(self):
        pid = "22222222-2222-2222-2222-222222222222"
        history = [
            {
                "action_type": "attack",
                "piece_id": pid,
                "result": {"damage": 100},
            },
        ]
        assert compute_xp(history).get(pid) == 100


class TestRemapIdsEvolveAndTrade:
    def test_evolve_in_place_preserves_uuid(self):
        state = empty_state()
        place(state, PieceType.PIKACHU, Team.RED, 4, 4)
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        id_map = {(4, 4): uid}
        move = make_move(PieceType.PIKACHU, 4, 4, ActionType.EVOLVE, 4, 4)
        [(ns, _)] = apply_move(state, move)
        new_map = remap_ids(state, ns, move, id_map)
        assert new_map.get((4, 4)) == uid

    def test_trade_eevee_evolution_keeps_target_uuid(self):
        state = empty_state(active=Team.BLUE)
        place(state, PieceType.SQUIRTLE, Team.BLUE, 3, 3)
        place(state, PieceType.EEVEE, Team.BLUE, 3, 4)
        uid_sq = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        uid_ee = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        id_map = {(3, 3): uid_sq, (3, 4): uid_ee}
        move = make_move(PieceType.SQUIRTLE, 3, 3, ActionType.TRADE, 3, 4)
        [(ns, _)] = apply_move(state, move)
        new_map = remap_ids(state, ns, move, id_map)
        assert new_map.get((3, 3)) == uid_sq
        assert new_map.get((3, 4)) == uid_ee
