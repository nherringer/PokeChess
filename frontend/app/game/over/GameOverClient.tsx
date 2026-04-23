"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { getGame } from "@/lib/api/games";
import { Button } from "@/components/ui/Button";
import { XpBar } from "@/components/ui/XpBar";
import { Spinner } from "@/components/ui/Spinner";
import type { GameDetail, MoveHistoryEntry } from "@/lib/types/api";
import { PIECE_TYPE_EMOJIS, PIECE_TYPE_LABELS } from "@/lib/constants";

interface XpResult {
  pieceId: string;
  pieceType: string;
  earned: number;
}

function computeXpResults(history: MoveHistoryEntry[]): XpResult[] {
  const byPiece: Record<string, { pieceType: string; damage: number }> = {};
  for (const entry of history) {
    if (!entry.piece_id) continue;
    const damage = (entry.result?.damage as number | null) ?? 0;
    if (!byPiece[entry.piece_id]) {
      byPiece[entry.piece_id] = {
        pieceType: (entry.result?.attacker_type as string | null) ?? "UNKNOWN",
        damage: 0,
      };
    }
    byPiece[entry.piece_id].damage += damage;
  }
  return Object.entries(byPiece)
    .map(([id, { pieceType, damage }]) => ({
      pieceId: id,
      pieceType,
      earned: Math.round(damage / 10),
    }))
    .filter((r) => r.earned > 0)
    .sort((a, b) => b.earned - a.earned);
}

interface XpResultRowProps {
  result: XpResult;
  index: number;
}

function XpResultRow({ result, index }: XpResultRowProps) {
  const emoji = PIECE_TYPE_EMOJIS[result.pieceType] ?? "?";
  const label = PIECE_TYPE_LABELS[result.pieceType] ?? result.pieceType;
  const threshold = 30;
  const progress = Math.min(result.earned, threshold);

  return (
    <div
      className="flex items-center gap-3 animate-fade-in-up"
      style={{ animationDelay: `${index * 80}ms`, animationFillMode: "both", opacity: 0 }}
    >
      <span style={{ fontSize: 24 }}>{emoji}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-white text-sm font-bold">{label}</span>
          <span className="text-accent-gold text-xs font-bold">+{result.earned} ⭐</span>
        </div>
        <XpBar current={progress} max={threshold} color="#FFD700" />
      </div>
    </div>
  );
}

export default function GameOverClient() {
  const params = useSearchParams();
  const router = useRouter();
  const gameId = params.get("gameId") ?? "";
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!gameId) return;
    getGame(gameId)
      .then(setGame)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [gameId]);

  if (loading) {
    return (
      <div className="h-screen bg-bg-deep flex items-center justify-center">
        <Spinner size={40} />
      </div>
    );
  }

  if (!game) {
    return (
      <div className="h-screen bg-bg-deep flex flex-col items-center justify-center gap-4">
        <p className="text-white/50">Game not found.</p>
        <Link href="/" className="text-blue-team underline">
          Go home
        </Link>
      </div>
    );
  }

  const winner = game.winner;
  const isDraw = winner === "draw";

  const winnerColor = winner === "red" ? "#E03737" : winner === "blue" ? "#3C72E0" : "#FFD700";
  const winnerLabel = isDraw
    ? "🤝 DRAW!"
    : winner === "red"
    ? "🏆 TEAM RED WINS!"
    : "🏆 TEAM BLUE WINS!";

  const kingEmoji = winner === "red" ? "⚡" : winner === "blue" ? "🌟" : "♟";

  const xpResults = computeXpResults(game.move_history);

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center px-6 py-12">
      <div className="text-center mb-8">
        <div
          className="font-display text-3xl font-bold mb-2 animate-bounce-scale"
          style={{ color: winnerColor }}
        >
          {winnerLabel}
        </div>
        <div className="text-5xl animate-bounce-scale" style={{ animationDelay: "0.1s" }}>
          {kingEmoji}
        </div>
        {game.end_reason && (
          <p className="mt-2 text-white/40 text-sm capitalize">
            {game.end_reason.replace(/_/g, " ")}
          </p>
        )}
      </div>

      {xpResults.length > 0 && (
        <div className="w-full max-w-sm bg-bg-card rounded-xl p-5 mb-8">
          <h3 className="font-display font-bold text-white mb-4">
            XP Earned This Game:
          </h3>
          <div className="flex flex-col gap-3">
            {xpResults.map((r, i) => (
              <XpResultRow key={r.pieceId} result={r} index={i} />
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 w-full max-w-sm">
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => router.push("/play")}
        >
          ▶ Play Again
        </Button>
        <Button
          variant="ghost"
          size="lg"
          fullWidth
          onClick={() => router.push("/")}
        >
          🏠 Home
        </Button>
      </div>
    </div>
  );
}
