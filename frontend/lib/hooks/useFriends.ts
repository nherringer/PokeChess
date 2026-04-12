"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getFriends } from "@/lib/api/friends";
import { ApiError } from "@/lib/api/client";
import type { FriendsResponse } from "@/lib/types/api";
import { POLL_INTERVAL_MS } from "@/lib/constants";

export function useFriends() {
  const [data, setData] = useState<FriendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unauthenticated, setUnauthenticated] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await getFriends();
      setData(result);
      setError(null);
      setUnauthenticated(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUnauthenticated(true);
        setError(null);
        // Stop polling — no point retrying without a valid session
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } else {
        setError(err instanceof Error ? err.message : "Failed to load friends");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  return { data, loading, error, unauthenticated, refresh };
}
