"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { PageShell } from "@/components/ui/PageShell";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { getGames } from "@/lib/api/games";
import type { GameSummary, GamesListResponse } from "@/lib/types/api";

function StatusBadge({ status }: { status: GameSummary["status"] }) {
  const colors: Record<GameSummary["status"], string> = {
    active: "bg-green-500/20 text-green-400",
    pending: "bg-yellow-500/20 text-yellow-400",
    complete: "bg-white/10 text-white/50",
  };
  return (
    <span className={["text-xs px-2 py-0.5 rounded-full font-bold", colors[status]].join(" ")}>
      {status}
    </span>
  );
}

function GameCard({ game }: { game: GameSummary }) {
  return (
    <div className="bg-bg-card rounded-xl p-4 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <StatusBadge status={game.status} />
          {game.is_bot_game && <span className="text-xs text-text-muted">vs Bot</span>}
          <span className="text-xs text-text-muted">Turn {game.turn_number}</span>
        </div>
        {game.whose_turn && game.status === "active" && (
          <p className="text-xs text-white/50">
            {game.whose_turn === "red" ? "🔴" : "🔵"}{" "}
            {game.whose_turn.charAt(0).toUpperCase() + game.whose_turn.slice(1)}&apos;s turn
          </p>
        )}
        {game.winner && (
          <p className="text-xs text-accent-gold">Winner: {game.winner}</p>
        )}
      </div>
      {game.status === "active" && (
        <Link href={`/game/${game.id}`}>
          <Button size="sm" variant="secondary">Resume</Button>
        </Link>
      )}
      {game.status === "complete" && (
        <Link href={`/game/over?gameId=${game.id}`}>
          <Button size="sm" variant="ghost">Review</Button>
        </Link>
      )}
    </div>
  );
}

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
                  <Link href="/play" className="text-poke-blue underline">Start one!</Link>
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {active.map((g) => <GameCard key={g.id} game={g} />)}
                </div>
              )}
            </section>

            <section>
              <h2 className="font-display font-bold text-white text-lg mb-3">Recent Games</h2>
              {completed.length === 0 ? (
                <p className="text-text-muted text-sm">No completed games yet.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {completed.map((g) => <GameCard key={g.id} game={g} />)}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
