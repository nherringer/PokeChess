"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/ui/PageShell";
import { Spinner } from "@/components/ui/Spinner";
import { createGame } from "@/lib/api/games";
import { useBots } from "@/lib/hooks/useBots";
import type { BotOut } from "@/lib/api/bots";

interface DifficultyTileProps {
  bot: BotOut;
  onSelect: () => void;
  loading: boolean;
}

function DifficultyTile({ bot, onSelect, loading }: DifficultyTileProps) {
  return (
    <button
      className="w-full bg-bg-card hover:bg-white/5 border border-white/10 rounded-xl px-5 py-4 flex items-center justify-between transition-all active:scale-[0.98] disabled:opacity-50"
      onClick={onSelect}
      disabled={loading}
    >
      <div className="text-left">
        <div className="font-display font-bold text-white text-lg">{bot.label}</div>
        <div className="text-text-muted text-sm mt-0.5">{bot.flavor}</div>
      </div>
      {loading ? (
        <Spinner size={20} />
      ) : (
        <span className="text-white/30 text-xl">▶</span>
      )}
    </button>
  );
}

export default function PlayPage() {
  const router = useRouter();
  const { bots, loading: botsLoading, error: botsError } = useBots();
  const [loadingBotId, setLoadingBotId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = async (bot: BotOut) => {
    setLoadingBotId(bot.id);
    setError(null);
    try {
      const game = await createGame({ bot_id: bot.id, player_side: "red" });
      router.push(`/game/${game.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create game");
      setLoadingBotId(null);
    }
  };

  return (
    <PageShell title="Choose Difficulty" showBack={false}>
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        <p className="text-text-muted text-sm mb-4">
          You play as Red (moves first).
        </p>

        {(error || botsError) && (
          <div className="mb-4 bg-red-team/20 border border-red-team/50 rounded-xl px-4 py-3 text-red-300 text-sm">
            {error ?? botsError}
          </div>
        )}

        {botsLoading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}

        {!botsLoading && (
          <div className="flex flex-col gap-3">
            {bots.map((bot) => (
              <DifficultyTile
                key={bot.id}
                bot={bot}
                onSelect={() => handleSelect(bot)}
                loading={loadingBotId === bot.id}
              />
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}
