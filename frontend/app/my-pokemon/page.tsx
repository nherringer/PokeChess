"use client";

import React, { useState, useEffect } from "react";
import { PageShell } from "@/components/ui/PageShell";
import { Badge } from "@/components/ui/Badge";
import { XpBar } from "@/components/ui/XpBar";
import { Spinner } from "@/components/ui/Spinner";
import { getMe } from "@/lib/api/me";
import type { PieceOut } from "@/lib/types/api";
import {
  PIECE_TYPE_EMOJIS,
  PIECE_TYPE_LABELS,
  POKEMON_TYPE_FOR_PIECE,
} from "@/lib/constants";

const ROLE_ORDER = ["KING", "QUEEN", "ROOK", "KNIGHT", "BISHOP", "PAWN"];
const XP_THRESHOLDS = [30, 100];

function getXpThreshold(stage: number): number {
  return XP_THRESHOLDS[stage] ?? 999;
}

interface PieceCardProps {
  piece: PieceOut;
  index: number;
  sameSpeCount: number;
}

function PieceCard({ piece, index, sameSpeCount }: PieceCardProps) {
  const emoji = PIECE_TYPE_EMOJIS[piece.species] ?? "?";
  const label = PIECE_TYPE_LABELS[piece.species] ?? piece.species;
  const type = POKEMON_TYPE_FOR_PIECE[piece.species];
  const threshold = getXpThreshold(piece.evolution_stage);

  return (
    <div
      className="bg-bg-card rounded-xl p-4 flex items-start gap-4 animate-fade-in-up"
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "both", opacity: 0 }}
    >
      <div className="w-16 h-16 rounded-full bg-bg-panel flex items-center justify-center border-2 border-poke-blue shrink-0">
        <span style={{ fontSize: 32 }}>{emoji}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-text-muted uppercase tracking-wide font-bold mb-0.5">
          {piece.role}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-display font-bold text-white">
            {label}
            {sameSpeCount > 1 && (
              <span className="text-white/30 text-sm"> #{index + 1}</span>
            )}
          </span>
          {type && <Badge type={type} />}
        </div>
        <div className="mt-2">
          <div className="flex justify-between text-xs text-text-muted mb-1">
            <span>XP</span>
            <span>{piece.xp}/{threshold}</span>
          </div>
          <XpBar current={piece.xp} max={threshold} color="#FFD700" />
        </div>
      </div>
    </div>
  );
}

export default function MyPokemonPage() {
  const [pieces, setPieces] = useState<PieceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then((profile) => setPieces(profile.pieces))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const sorted = [...pieces].sort((a, b) => {
    const ai = ROLE_ORDER.indexOf(a.role);
    const bi = ROLE_ORDER.indexOf(b.role);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  const speciesSeen: Record<string, number> = {};
  const pieceIndexes = sorted.map((p) => {
    const count = speciesSeen[p.species] ?? 0;
    speciesSeen[p.species] = count + 1;
    return count;
  });

  const speciesCounts = pieces.reduce<Record<string, number>>((acc, p) => {
    acc[p.species] = (acc[p.species] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <PageShell title="My Pokémon" showBack={false}>
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        {loading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {error && (
          <div className="text-center py-8 text-red-team text-sm">{error}</div>
        )}
        {!loading && !error && pieces.length === 0 && (
          <div className="text-center py-16 text-text-muted">
            No Pokémon yet. Start a game!
          </div>
        )}
        {!loading && !error && (
          <div className="flex flex-col gap-3">
            {sorted.map((piece, i) => (
              <PieceCard
                key={piece.id}
                piece={piece}
                index={pieceIndexes[i]}
                sameSpeCount={speciesCounts[piece.species] ?? 1}
              />
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}
