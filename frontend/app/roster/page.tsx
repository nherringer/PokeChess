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
import { PokemonSpriteAvatar } from "@/components/ui/PokemonSpriteAvatar";

const ROLE_ORDER = ["king", "queen", "rook", "knight", "bishop", "pawn"];
const XP_THRESHOLDS = [30, 100];

function getXpThreshold(stage: number): number {
  return XP_THRESHOLDS[stage] ?? 999;
}

function sortByRole(pieces: PieceOut[]): PieceOut[] {
  return [...pieces].sort((a, b) => {
    const ai = ROLE_ORDER.indexOf(a.role.toLowerCase());
    const bi = ROLE_ORDER.indexOf(b.role.toLowerCase());
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
}

interface PieceCardProps {
  piece: PieceOut;
  index: number;
  sameSpeCount: number;
  animIndex: number;
}

function PieceCard({ piece, index, sameSpeCount, animIndex }: PieceCardProps) {
  const emoji = PIECE_TYPE_EMOJIS[piece.species] ?? "?";
  const label = PIECE_TYPE_LABELS[piece.species] ?? piece.species;
  const type = POKEMON_TYPE_FOR_PIECE[piece.species];
  const threshold = getXpThreshold(piece.evolution_stage);
  const borderColor = piece.set_side === "red" ? "border-red-team" : "border-poke-blue";

  return (
    <div
      className="bg-bg-card rounded-xl p-4 flex items-start gap-4 animate-fade-in-up"
      style={{ animationDelay: `${animIndex * 60}ms`, animationFillMode: "both", opacity: 0 }}
    >
      <PokemonSpriteAvatar
        speciesOrPieceType={piece.species}
        emojiFallback={emoji}
        sizePx={64}
        className={`border-2 ${borderColor}`}
      />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-white/40 uppercase tracking-wide font-bold mb-0.5">
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
          <div className="flex justify-between text-xs text-white/40 mb-1">
            <span>XP</span>
            <span>
              {piece.xp}/{threshold}
            </span>
          </div>
          <XpBar current={piece.xp} max={threshold} color="#FFD700" />
        </div>
      </div>
    </div>
  );
}

interface SetGroupProps {
  pieces: PieceOut[];
  side: "red" | "blue";
  animOffset: number;
}

function SetGroup({ pieces, side, animOffset }: SetGroupProps) {
  const sorted = sortByRole(pieces);
  const speciesCounts = pieces.reduce<Record<string, number>>((acc, p) => {
    acc[p.species] = (acc[p.species] ?? 0) + 1;
    return acc;
  }, {});
  const speciesSeen: Record<string, number> = {};
  const pieceIndexes = sorted.map((p) => {
    const count = speciesSeen[p.species] ?? 0;
    speciesSeen[p.species] = count + 1;
    return count;
  });

  const labelColor = side === "red" ? "text-red-team" : "text-poke-blue";
  const label = side === "red" ? "Red Set — Pikachu" : "Blue Set — Eevee";

  return (
    <div>
      <h2 className={`mb-3 text-sm font-bold uppercase tracking-widest ${labelColor} border-b border-white/10 pb-1`}>
        {label}
      </h2>
      <div className="flex flex-col gap-3">
        {sorted.map((piece, i) => (
          <PieceCard
            key={piece.id}
            piece={piece}
            index={pieceIndexes[i]}
            sameSpeCount={speciesCounts[piece.species] ?? 1}
            animIndex={animOffset + i}
          />
        ))}
      </div>
    </div>
  );
}

export default function RosterPage() {
  const [pieces, setPieces] = useState<PieceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then((profile) => setPieces(profile.pieces))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load")
      )
      .finally(() => setLoading(false));
  }, []);

  const redPieces = pieces.filter((p) => p.set_side === "red");
  const bluePieces = pieces.filter((p) => p.set_side === "blue");
  const hasAnyPieces = redPieces.length > 0 || bluePieces.length > 0;

  return (
    <PageShell title="My Pokémon">
      <div className="px-4 pt-4 pb-8 max-w-lg mx-auto">
        {loading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {error && (
          <div className="text-center py-8 text-red-400 text-sm">{error}</div>
        )}
        {!loading && !error && !hasAnyPieces && (
          <div className="text-center py-16 text-white/40">
            No Pokémon yet. Start a game!
          </div>
        )}
        {!loading && !error && hasAnyPieces && (
          <div className="flex flex-col gap-8">
            {redPieces.length > 0 && (
              <SetGroup pieces={redPieces} side="red" animOffset={0} />
            )}
            {bluePieces.length > 0 && (
              <SetGroup pieces={bluePieces} side="blue" animOffset={redPieces.length} />
            )}
          </div>
        )}
      </div>
    </PageShell>
  );
}
