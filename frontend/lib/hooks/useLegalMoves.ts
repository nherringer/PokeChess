"use client";

import { useState, useCallback } from "react";
import { getLegalMoves } from "@/lib/api/moves";
import { useGameStore } from "@/lib/store/gameStore";

export function useLegalMoves(gameId: string | null) {
  const [loading, setLoading] = useState(false);
  const setLegalMoves = useGameStore((s) => s.setLegalMoves);

  const fetchMoves = useCallback(
    async (row: number, col: number) => {
      if (!gameId) return;
      setLoading(true);
      try {
        const moves = await getLegalMoves(gameId, row, col);
        setLegalMoves(moves);
      } catch {
        setLegalMoves([]);
      } finally {
        setLoading(false);
      }
    },
    [gameId, setLegalMoves]
  );

  return { fetchMoves, loading };
}
