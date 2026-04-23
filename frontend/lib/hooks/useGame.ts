"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getGame } from "@/lib/api/games";
import type { GameDetail } from "@/lib/types/api";
import { POLL_INTERVAL_MS } from "@/lib/constants";

export function useGame(gameId: string | null) {
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    if (!gameId) return;
    try {
      const result = await getGame(gameId);
      setGame(result);
      setError(null);
      if (result.status === "complete") {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load game");
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => {
    if (!gameId) {
      setLoading(false);
      return;
    }
    fetch();
    intervalRef.current = setInterval(fetch, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetch, gameId]);

  return { game, loading, error };
}
