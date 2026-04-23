"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/ui/PageShell";
import { Spinner } from "@/components/ui/Spinner";
import { createGame } from "@/lib/api/games";
import { useBots } from "@/lib/hooks/useBots";
import type { BotOut } from "@/lib/api/bots";

// ─── Types ───────────────────────────────────────────────────────────────────

type FreeSide = "red" | "blue" | "random";

// ─── PersonaCard ─────────────────────────────────────────────────────────────

interface PersonaCardProps {
  bot: BotOut;
  selected: boolean;
  onSelect: () => void;
}

function PersonaCard({ bot, selected, onSelect }: PersonaCardProps) {
  const accent = bot.accent_color;

  return (
    <button
      onClick={onSelect}
      className={[
        "w-full text-left rounded-xl border transition-all active:scale-[0.98]",
        "flex items-center gap-4 px-4 py-3",
        selected
          ? "bg-white/8 border-white/40"
          : "bg-bg-card hover:bg-white/5 border-white/10",
      ].join(" ")}
      style={selected ? { borderColor: accent, boxShadow: `0 0 0 1px ${accent}22` } : {}}
    >
      {/* Left accent bar */}
      <div
        className="w-1 self-stretch rounded-full shrink-0"
        style={{ backgroundColor: accent }}
      />

      {/* Trainer portrait */}
      {bot.trainer_sprite ? (
        <img
          src={`/sprites/trainers/${bot.trainer_sprite}`}
          alt={bot.name}
          className="w-14 h-14 object-contain shrink-0"
        />
      ) : (
        <div className="w-14 h-14 shrink-0" />
      )}

      {/* Text column */}
      <div className="flex-1 min-w-0">
        {/* Name */}
        <div
          className="font-display font-bold text-base leading-tight"
          style={{ color: accent }}
        >
          {bot.name}
        </div>

        {/* Difficulty dots */}
        <div className="flex items-center gap-1 mt-1">
          {Array.from({ length: 6 }, (_, i) => (
            <span
              key={i}
              className="inline-block w-2 h-2 rounded-full"
              style={{
                backgroundColor: i < bot.stars ? accent : "transparent",
                border: `1px solid ${i < bot.stars ? accent : "#444"}`,
              }}
            />
          ))}
          <span className="ml-1 text-[11px] text-white/40">
            {["", "Beginner", "Sneaky", "Balanced", "Strategic", "Expert", "LEGEND"][bot.stars]}
          </span>
        </div>

        {/* Flavor text */}
        <div className="text-white/50 text-xs mt-1 truncate">
          &ldquo;{bot.flavor}&rdquo;
        </div>

        {/* Forced-side warning */}
        {bot.forced_player_side && (
          <div className="mt-1 text-[11px] font-semibold text-yellow-400">
            ⚠ You play as {bot.forced_player_side.toUpperCase()}
          </div>
        )}
      </div>
    </button>
  );
}

// ─── SidePicker ──────────────────────────────────────────────────────────────

interface SidePickerProps {
  selected: FreeSide | null;
  onChange: (side: FreeSide) => void;
}

function SidePicker({ selected, onChange }: SidePickerProps) {
  const options: { value: FreeSide; label: string; color: string }[] = [
    { value: "red",    label: "RED",    color: "#d93737" },
    { value: "blue",   label: "BLUE",   color: "#3b5ee5" },
    { value: "random", label: "RANDOM", color: "#888" },
  ];

  return (
    <div className="flex gap-2 justify-center">
      {options.map(({ value, label, color }) => {
        const active = selected === value;
        return (
          <button
            key={value}
            onClick={() => onChange(value)}
            className="px-4 py-2 rounded-lg text-sm font-bold border transition-all"
            style={{
              borderColor: color,
              color: active ? "#fff" : color,
              backgroundColor: active ? color : "transparent",
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

// ─── PlayPage ─────────────────────────────────────────────────────────────────

export default function PlayPage() {
  const router = useRouter();
  const { bots, loading: botsLoading, error: botsError } = useBots();

  const [selectedBot, setSelectedBot]     = useState<BotOut | null>(null);
  const [selectedSide, setSelectedSide]   = useState<FreeSide | null>(null);
  const [starting, setStarting]           = useState(false);
  const [error, setError]                 = useState<string | null>(null);

  // When a new persona is selected, reset the side choice (unless it's forced).
  const handleSelectBot = (bot: BotOut) => {
    setSelectedBot(bot);
    setError(null);
    if (bot.forced_player_side) {
      setSelectedSide(bot.forced_player_side as FreeSide);
    } else {
      setSelectedSide(null);
    }
  };

  const canStart = selectedBot !== null && selectedSide !== null;

  const handleStart = async () => {
    if (!selectedBot || !selectedSide) return;
    setStarting(true);
    setError(null);
    try {
      // Resolve "random" client-side so the player sees their actual side in the game.
      const resolvedSide: "red" | "blue" =
        selectedSide === "random"
          ? Math.random() < 0.5 ? "red" : "blue"
          : selectedSide;

      const game = await createGame({ bot_id: selectedBot.id, player_side: resolvedSide });
      router.push(`/game?id=${game.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start game");
      setStarting(false);
    }
  };

  return (
    <PageShell title="Choose Opponent" showBack={false}>
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">

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
          <>
            {/* Persona grid */}
            <div className="flex flex-col gap-3 mb-6">
              {bots.map((bot) => (
                <PersonaCard
                  key={bot.id}
                  bot={bot}
                  selected={selectedBot?.id === bot.id}
                  onSelect={() => handleSelectBot(bot)}
                />
              ))}
            </div>

            {/* Side selection — appears after a persona is chosen */}
            {selectedBot && (
              <div className="mb-6 rounded-xl border border-white/10 bg-bg-card px-5 py-4 flex flex-col gap-3">
                {selectedBot.forced_player_side ? (
                  <p className="text-center text-sm font-semibold text-yellow-400">
                    ⚠ Team locked — you play as{" "}
                    <span className={selectedBot.forced_player_side === "red" ? "text-red-team" : "text-blue-team"}>
                      {selectedBot.forced_player_side.toUpperCase()}
                    </span>
                  </p>
                ) : (
                  <>
                    <p className="text-center text-white/60 text-sm">Choose your team</p>
                    <SidePicker selected={selectedSide} onChange={setSelectedSide} />
                  </>
                )}

                <button
                  onClick={handleStart}
                  disabled={!canStart || starting}
                  className="mt-1 w-full py-3 rounded-xl font-display font-bold text-white text-base transition-all disabled:opacity-40"
                  style={{ backgroundColor: selectedBot.accent_color }}
                >
                  {starting ? <Spinner size={20} /> : "Start Game"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
