import { apiFetch } from "./client";
import type { LegalMoveOut, MovePayload, GameDetail } from "@/lib/types/api";

export async function getLegalMoves(
  gameId: string,
  pieceRow: number,
  pieceCol: number
): Promise<LegalMoveOut[]> {
  return apiFetch<LegalMoveOut[]>(
    `/games/${gameId}/legal_moves?piece_row=${pieceRow}&piece_col=${pieceCol}`
  );
}

export async function submitMove(
  gameId: string,
  payload: MovePayload
): Promise<GameDetail> {
  return apiFetch<GameDetail>(`/games/${gameId}/move`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function retryBotMove(gameId: string): Promise<void> {
  await apiFetch<unknown>(`/games/${gameId}/retry-bot-move`, { method: "POST" });
}
