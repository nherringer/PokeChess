"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getGame } from "@/lib/api/games";
import type { GameDetail } from "@/lib/types/api";
import { POLL_INTERVAL_MS, BOT_POLL_INTERVAL_MS } from "@/lib/constants";

function pollDelay(game: GameDetail | null): number {
  if (game?.is_bot_game && game.whose_turn === game.bot_side) {
    return BOT_POLL_INTERVAL_MS;
  }
  return POLL_INTERVAL_MS;
}

export function useGame(gameId: string | null) {
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Ref so the timeout callback always calls the latest fetch without being
  // listed as an effect dependency (avoids resetting the timer on every render).
  const fetchRef = useRef<(() => Promise<void>) | undefined>(undefined);
  const activeRef = useRef(true);

  const fetch = useCallback(async () => {
    if (!gameId) return;
    try {
      const result = await getGame(gameId);
      setGame(result);
      setError(null);
      if (result.status !== "complete" && activeRef.current) {
        timeoutRef.current = setTimeout(
          () => fetchRef.current?.(),
          pollDelay(result),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load game");
      if (activeRef.current) {
        timeoutRef.current = setTimeout(
          () => fetchRef.current?.(),
          POLL_INTERVAL_MS,
        );
      }
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  // Keep ref in sync so scheduled timeouts always invoke the latest closure.
  fetchRef.current = fetch;

  useEffect(() => {
    if (!gameId) {
      setLoading(false);
      return;
    }
    activeRef.current = true;
    fetch();
    return () => {
      activeRef.current = false;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [fetch, gameId]);

  return { game, loading, error };
}
