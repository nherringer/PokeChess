"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getInvites } from "@/lib/api/invites";
import type { InviteOut } from "@/lib/types/api";
import { POLL_INTERVAL_MS } from "@/lib/constants";

export function useInvites() {
  const [data, setData] = useState<InviteOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await getInvites();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load invites");
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

  return { data, loading, error };
}
