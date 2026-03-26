"""
PokeChess Bot Benchmark — statistical win-rate validation (Task #11).

Runs bot vs random and bot vs bot matchups, prints win rates with 95%
Wilson-score confidence intervals.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --budget 1.0 --games 50
    python scripts/benchmark.py --budget 3.0 --games 100 --seed 0

Interpreting results:
    Bot (RED) vs Random (BLUE)  — expect RED CI clearly above 50 %
    Random (RED) vs Bot (BLUE)  — expect BLUE CI clearly above 50 %
    Bot vs Bot (independent)    — expect roughly 50/50 (RED first-move edge)
    Bot vs Bot (shared table)   — same, but warm-started from prior games
"""
import argparse
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state import GameState, Team
from engine.moves import get_legal_moves
from engine.rules import apply_move, is_terminal, hp_winner
from bot.mcts import MCTS
from bot.transposition import TranspositionTable


# ---------------------------------------------------------------------------
# Game runner
# ---------------------------------------------------------------------------

def play_game(red_fn, blue_fn, max_turns: int = 300) -> tuple:
    """
    Play one full game.
    Returns (winner: Team | None, half_moves: int).
    winner is None for draw or hp_winner tie at depth limit.
    """
    state = GameState.new_game()
    half_moves = 0
    for _ in range(max_turns):
        done, winner = is_terminal(state)
        if done:
            return winner, half_moves
        moves = get_legal_moves(state)
        if not moves:
            return None, half_moves
        fn   = red_fn if state.active_player == Team.RED else blue_fn
        move = fn(state)
        outcomes = apply_move(state, move)
        state = random.choices(
            [s for s, _ in outcomes], weights=[p for _, p in outcomes]
        )[0]
        half_moves += 1
    return hp_winner(state), half_moves


def random_fn(state):
    return random.choice(get_legal_moves(state))


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple:
    """95 % Wilson-score confidence interval for a proportion k/n."""
    if n == 0:
        return 0.0, 1.0
    p      = k / n
    denom  = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


# ---------------------------------------------------------------------------
# Matchup runner
# ---------------------------------------------------------------------------

def run_matchup(
    label: str,
    red_factory,
    blue_factory,
    n_games: int,
    max_turns: int,
) -> dict:
    """
    Play n_games, print a live progress line, then a results summary.
    red_factory / blue_factory: callable() -> move_fn  (called once per game).
    Returns a results dict.
    """
    W = 56
    print(f"\n{'─' * W}")
    print(f"  {label}")
    print(f"  {n_games} games  |  max {max_turns} half-moves each")
    print(f"{'─' * W}")

    red_wins = blue_wins = draws = 0
    total_turns = 0
    t0 = time.monotonic()

    for i in range(n_games):
        red_fn  = red_factory()
        blue_fn = blue_factory()
        winner, turns = play_game(red_fn, blue_fn, max_turns=max_turns)
        total_turns += turns

        if   winner == Team.RED:  red_wins  += 1; sym = 'R'
        elif winner == Team.BLUE: blue_wins += 1; sym = 'B'
        else:                     draws     += 1; sym = '='

        elapsed = time.monotonic() - t0
        eta_s   = elapsed / (i + 1) * (n_games - i - 1)
        print(
            f"  [{i+1:3d}/{n_games}]  R:{red_wins:3d}  B:{blue_wins:3d}"
            f"  D:{draws:2d}  last:{sym}  ETA {eta_s:5.0f}s",
            end='\r',
        )

    elapsed = time.monotonic() - t0
    print(' ' * 72, end='\r')   # clear progress line

    lo_r, hi_r = wilson_ci(red_wins,  n_games)
    lo_b, hi_b = wilson_ci(blue_wins, n_games)
    avg_t = total_turns / n_games if n_games else 0

    print(f"  RED  wins: {red_wins:3d}/{n_games}"
          f"  ({100*red_wins/n_games:5.1f}%)"
          f"  95% CI [{100*lo_r:.1f}%, {100*hi_r:.1f}%]")
    print(f"  BLUE wins: {blue_wins:3d}/{n_games}"
          f"  ({100*blue_wins/n_games:5.1f}%)"
          f"  95% CI [{100*lo_b:.1f}%, {100*hi_b:.1f}%]")
    print(f"  Draws:     {draws:3d}/{n_games}"
          f"  ({100*draws/n_games:5.1f}%)")
    print(f"  Avg half-moves: {avg_t:.0f}   Wall time: {elapsed:.0f}s")

    return dict(
        red_wins=red_wins, blue_wins=blue_wins, draws=draws,
        n=n_games, avg_turns=avg_t, elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description='PokeChess bot win-rate benchmark',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument('--budget',    type=float, default=0.5,
                    help='MCTS time budget per move (seconds)')
    ap.add_argument('--games',     type=int,   default=20,
                    help='Number of games per matchup')
    ap.add_argument('--max-turns', type=int,   default=300,
                    help='Half-move cap before hp_winner tiebreak')
    ap.add_argument('--seed',      type=int,   default=42,
                    help='Random seed')
    args = ap.parse_args()

    random.seed(args.seed)
    b, n, t = args.budget, args.games, args.max_turns

    print(f"\n{'=' * 56}")
    print(f"  PokeChess Bot Benchmark")
    print(f"  MCTS budget: {b} s/move  |  Games/matchup: {n}")
    print(f"  Max half-moves: {t}  |  Seed: {args.seed}")
    print(f"{'=' * 56}")

    results = {}

    # 1. Bot (RED) vs random (BLUE)
    results['bot_r_rand_b'] = run_matchup(
        "Bot (RED) vs Random (BLUE)",
        red_factory=lambda: MCTS(time_budget=b).select_move,
        blue_factory=lambda: random_fn,
        n_games=n, max_turns=t,
    )

    # 2. Random (RED) vs bot (BLUE)
    results['rand_r_bot_b'] = run_matchup(
        "Random (RED) vs Bot (BLUE)",
        red_factory=lambda: random_fn,
        blue_factory=lambda: MCTS(time_budget=b).select_move,
        n_games=n, max_turns=t,
    )

    # 3. Bot vs bot — independent tables
    results['bot_vs_bot'] = run_matchup(
        "Bot (RED) vs Bot (BLUE)  [independent tables]",
        red_factory=lambda: MCTS(time_budget=b).select_move,
        blue_factory=lambda: MCTS(time_budget=b).select_move,
        n_games=n, max_turns=t,
    )

    # 4. Bot vs bot — shared transposition table (inter-game learning)
    tt = TranspositionTable()
    results['bot_vs_bot_shared_tt'] = run_matchup(
        "Bot (RED) vs Bot (BLUE)  [shared transposition table]",
        red_factory=lambda: MCTS(time_budget=b, transposition=tt).select_move,
        blue_factory=lambda: MCTS(time_budget=b, transposition=tt).select_move,
        n_games=n, max_turns=t,
    )
    print(f"\n  Transposition table size after {n} games: {len(tt):,} entries")

    # Summary
    print(f"\n{'=' * 56}")
    print("  Summary (RED win % vs Random)")
    r1 = results['bot_r_rand_b']
    r2 = results['rand_r_bot_b']
    lo1, hi1 = wilson_ci(r1['red_wins'],  n)
    lo2, hi2 = wilson_ci(r2['blue_wins'], n)
    print(f"  Bot as RED  : {100*r1['red_wins']/n:5.1f}%"
          f"  CI [{100*lo1:.1f}%, {100*hi1:.1f}%]")
    print(f"  Bot as BLUE : {100*r2['blue_wins']/n:5.1f}%"
          f"  CI [{100*lo2:.1f}%, {100*hi2:.1f}%]")
    print(f"{'=' * 56}\n")


if __name__ == '__main__':
    main()
