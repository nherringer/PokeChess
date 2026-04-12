"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/ui/PageShell";
import { Spinner } from "@/components/ui/Spinner";
import { createGame } from "@/lib/api/games";
import { DIFFICULTY_CONFIG, BOT_IDS } from "@/lib/constants";

interface DifficultyTileProps {
  label: string;
  flavor: string;
  botName: string;
  onSelect: () => void;
  loading: boolean;
}

function DifficultyTile({
  label,
  flavor,
  onSelect,
  loading,
}: DifficultyTileProps) {
  return (
    <button
      className="w-full bg-bg-card hover:bg-white/5 border border-white/10 rounded-xl px-5 py-4 flex items-center justify-between transition-all active:scale-[0.98] disabled:opacity-50"
      onClick={onSelect}
      disabled={loading}
    >
      <div className="text-left">
        <div className="font-display font-bold text-white text-lg">{label}</div>
        <div className="text-white/40 text-sm mt-0.5">{flavor}</div>
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
  const [loadingIndex, setLoadingIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = async (index: number) => {
    const config = DIFFICULTY_CONFIG[index];
    setLoadingIndex(index);
    setError(null);
    try {
      const botId = BOT_IDS[config.botName] || "PLACEHOLDER";
      const game = await createGame({ bot_id: botId, player_side: "red" });
      router.push(`/game/${game.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create game");
      setLoadingIndex(null);
    }
  };

  return (
    <PageShell title="Choose Difficulty">
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        <p className="text-white/40 text-sm mb-4">
          You play as Red (moves first).
        </p>

        {error && (
          <div className="mb-4 bg-red-team/20 border border-red-team/50 rounded-xl px-4 py-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3">
          {DIFFICULTY_CONFIG.map((config, i) => (
            <DifficultyTile
              key={config.botName}
              label={config.label}
              flavor={config.flavor}
              botName={config.botName}
              onSelect={() => handleSelect(i)}
              loading={loadingIndex === i}
            />
          ))}
        </div>
      </div>
    </PageShell>
  );
}
