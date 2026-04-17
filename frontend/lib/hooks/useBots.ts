"use client";

import { useState, useEffect } from "react";
import { getBots } from "@/lib/api/bots";
import type { BotOut } from "@/lib/api/bots";

export function useBots() {
  const [bots, setBots] = useState<BotOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBots()
      .then(setBots)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load bots"))
      .finally(() => setLoading(false));
  }, []);

  return { bots, loading, error };
}
