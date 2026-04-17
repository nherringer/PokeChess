"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { PageShell } from "@/components/ui/PageShell";
import { Spinner } from "@/components/ui/Spinner";
import { getGames } from "@/lib/api/games";
import type { GamesListResponse } from "@/lib/types/api";
import { GameListCard } from "@/components/games/GameListCard";

export default function MyGamesPage() {
  const [data, setData] = useState<GamesListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGames()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load games"))
      .finally(() => setLoading(false));
  }, []);

  const active = data?.active ?? [];
  const completed = (data?.completed ?? []).slice(0, 10);

  return (
    <PageShell title="My Games" showBack={false}>
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        {loading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {error && (
          <div className="text-center py-8 text-red-team text-sm">{error}</div>
        )}

        {!loading && !error && (
          <>
            <section className="mb-6">
              <h2 className="font-display font-bold text-white text-lg mb-3">Active Games</h2>
              {active.length === 0 ? (
                <p className="text-text-muted text-sm">
                  No active games.{" "}
                  <Link href="/play" className="text-poke-blue underline">
                    Start one!
                  </Link>
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {active.map((g) => (
                    <GameListCard key={g.id} game={g} />
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="font-display font-bold text-white text-lg mb-3">Recent Games</h2>
              {completed.length === 0 ? (
                <p className="text-text-muted text-sm">No completed games yet.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {completed.map((g) => (
                    <GameListCard key={g.id} game={g} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
