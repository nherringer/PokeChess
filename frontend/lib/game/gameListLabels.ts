import type { GameSummary } from "@/lib/types/api";

export function opponentHeadline(game: GameSummary): string {
  if (game.opponent_display) {
    return `vs ${game.opponent_display}`;
  }
  return game.is_bot_game ? "vs Bot" : "vs Opponent";
}

/** Clear turn copy: ties whose_turn to you vs opponent (requires my_side from API). */
export function activeTurnLabel(game: GameSummary): string | null {
  if (game.status !== "active" || !game.whose_turn) return null;
  const team = game.whose_turn === "red" ? "Red" : "Blue";
  if (!game.my_side) {
    return `${team} to move`;
  }
  const isYours = game.whose_turn === game.my_side;
  if (isYours) {
    return `Your turn — ${team}`;
  }
  const name = game.opponent_display ?? "Opponent";
  return `Waiting for ${name} — ${team} to move`;
}

export function completedResultLabel(game: GameSummary): string | null {
  if (game.status !== "complete" || !game.winner) return null;
  if (game.winner === "draw") return "Draw";
  if (!game.my_side) {
    return `${game.winner === "red" ? "Red" : "Blue"} won`;
  }
  if (game.winner === game.my_side) return "You won";
  return `${game.opponent_display ?? "Opponent"} won`;
}
