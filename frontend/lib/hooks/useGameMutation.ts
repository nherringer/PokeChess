"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { submitMove as apiSubmitMove, getLegalMoves as apiGetLegalMoves, retryBotMove as apiRetryBotMove } from "@/lib/api/moves";
import { resignGame as apiResignGame } from "@/lib/api/games";
import { useGameStore } from "@/lib/store/gameStore";
import type { MovePayload } from "@/lib/types/api";

export function useGameMutation(gameId: string | null) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { setGame, localPlayerSide, clearSelection, setPendingPokeball } =
    useGameStore();

  const submitMove = useCallback(
    async (payload: MovePayload) => {
      if (!gameId || !localPlayerSide) return;
      setLoading(true);
      setError(null);
      try {
        const updatedGame = await apiSubmitMove(gameId, payload);

        // Check if latest move was a pokeball attack
        const lastMove = updatedGame.move_history.at(-1);
        if (
          lastMove &&
          (lastMove.action_type === "pokeball_attack" ||
            lastMove.action_type === "POKEBALL_ATTACK" ||
            lastMove.action_type === "masterball_attack" ||
            lastMove.action_type === "MASTERBALL_ATTACK")
        ) {
          // Set pending pokeball cell for animation
          if (
            lastMove.to_row !== undefined &&
            lastMove.to_col !== undefined
          ) {
            setPendingPokeball({ row: lastMove.to_row, col: lastMove.to_col });
          }
          // Still update game state
          setGame(updatedGame, localPlayerSide);
        } else {
          setGame(updatedGame, localPlayerSide);
        }

        clearSelection();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit move");
      } finally {
        setLoading(false);
      }
    },
    [gameId, localPlayerSide, setGame, clearSelection, setPendingPokeball]
  );

  const resign = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      await apiResignGame(gameId);
      router.push(`/game/over?gameId=${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resign");
    } finally {
      setLoading(false);
    }
  }, [gameId, router]);

  const retryBotMove = useCallback(async () => {
    if (!gameId) return;
    try {
      await apiRetryBotMove(gameId);
    } catch {
      // Polling will surface any persistent failure; swallow here to avoid
      // noisy errors from the automatic retry trigger.
    }
  }, [gameId]);

  // Unused but exported per spec
  void apiGetLegalMoves;

  return { submitMove, resign, retryBotMove, loading, error };
}
