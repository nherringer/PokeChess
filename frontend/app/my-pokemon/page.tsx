"use client";

import React, { useState, useEffect, useMemo } from "react";
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

const XP_THRESHOLDS = [30, 100];

function getXpThreshold(stage: number): number {
  return XP_THRESHOLDS[stage] ?? 999;
}

/** Standard chess back rank left → right: R N B Q K B N R */
const BACK_RANK_SLOTS = [
  "rook",
  "knight",
  "bishop",
  "queen",
  "king",
  "bishop",
  "knight",
  "rook",
] as const;

const FILE_LABELS = ["a", "b", "c", "d", "e", "f", "g", "h"];

function normRole(role: string): string {
  return role.toLowerCase();
}

/** Order pieces like a back rank; append any leftover roles at the end. */
function orderBackRank(pieces: PieceOut[]): PieceOut[] {
  const pools = new Map<string, PieceOut[]>();
  for (const p of pieces) {
    const r = normRole(p.role);
    if (!pools.has(r)) pools.set(r, []);
    pools.get(r)!.push(p);
  }
  for (const arr of pools.values()) {
    arr.sort((a, b) => a.id.localeCompare(b.id));
  }
  const out: PieceOut[] = [];
  for (const role of BACK_RANK_SLOTS) {
    const pool = pools.get(role);
    const next = pool?.shift();
    if (next) out.push(next);
  }
  const rest = [...pools.values()].flat();
  return [...out, ...rest];
}

interface RankCellProps {
  piece: PieceOut;
  fileLabel: string;
  sameSpeCount: number;
  pieceIndex: number;
  side: "red" | "blue";
}

function RankCell({ piece, fileLabel, sameSpeCount, pieceIndex, side }: RankCellProps) {
  const sk = piece.species.toUpperCase();
  const emoji = PIECE_TYPE_EMOJIS[sk] ?? "?";
  const label = PIECE_TYPE_LABELS[sk] ?? piece.species;
  const type = POKEMON_TYPE_FOR_PIECE[sk];
  const threshold = getXpThreshold(piece.evolution_stage);
  const borderColor = side === "red" ? "border-red-team" : "border-poke-blue";

  return (
    <div className="flex w-[4.5rem] shrink-0 flex-col items-center gap-1">
      <span className="text-[10px] font-mono text-text-muted/80">{fileLabel}</span>
      <div className="w-full rounded-lg border border-white/10 bg-bg-deep/80 px-1.5 py-2 flex flex-col items-center">
        <PokemonSpriteAvatar
          speciesOrPieceType={piece.species}
          emojiFallback={emoji}
          sizePx={56}
          className={`border-2 ${borderColor}`}
        />
        <span className="mt-1.5 text-center font-display text-[11px] font-bold leading-tight text-white line-clamp-2">
          {label}
          {sameSpeCount > 1 && (
            <span className="text-white/35"> #{pieceIndex + 1}</span>
          )}
        </span>
        {type && (
          <div className="mt-0.5 scale-90">
            <Badge type={type} />
          </div>
        )}
        <div className="mt-1.5 w-full px-0.5">
          <div className="mb-0.5 flex justify-between text-[9px] text-text-muted">
            <span>XP</span>
            <span>
              {piece.xp}/{threshold}
            </span>
          </div>
          <XpBar current={piece.xp} max={threshold} color="#FFD700" className="h-1.5" />
        </div>
      </div>
    </div>
  );
}

interface SetRowProps {
  pieces: PieceOut[];
  side: "red" | "blue";
}

function SetRow({ pieces, side }: SetRowProps) {
  const ordered = useMemo(() => orderBackRank(pieces), [pieces]);

  const speciesCounts = useMemo(
    () =>
      ordered.reduce<Record<string, number>>((acc, p) => {
        acc[p.species] = (acc[p.species] ?? 0) + 1;
        return acc;
      }, {}),
    [ordered]
  );

  const speciesSeen: Record<string, number> = {};
  const pieceIndexes = ordered.map((p) => {
    const count = speciesSeen[p.species] ?? 0;
    speciesSeen[p.species] = count + 1;
    return count;
  });

  const labelColor = side === "red" ? "text-red-team" : "text-poke-blue";
  const label = side === "red" ? "Red Set — Pikachu" : "Blue Set — Eevee";

  return (
    <div>
      <p className={`mb-2 text-center text-xs font-bold uppercase tracking-widest ${labelColor}`}>
        {label}
      </p>
      <div className="overflow-x-auto pb-2 [-webkit-overflow-scrolling:touch]">
        <div className="mx-auto flex w-min min-w-full justify-center gap-1.5 px-1 sm:gap-2">
          {ordered.map((piece, i) => (
            <RankCell
              key={piece.id}
              piece={piece}
              fileLabel={FILE_LABELS[i] ?? `${i + 1}`}
              sameSpeCount={speciesCounts[piece.species] ?? 1}
              pieceIndex={pieceIndexes[i]}
              side={side}
            />
          ))}
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

  const redPieces = useMemo(() => pieces.filter((p) => p.set_side === "red"), [pieces]);
  const bluePieces = useMemo(() => pieces.filter((p) => p.set_side === "blue"), [pieces]);
  const hasAnyPieces = redPieces.length > 0 || bluePieces.length > 0;

  return (
    <PageShell title="My Pokémon" showBack={false}>
      <div className="mx-auto max-w-3xl px-4 pb-8 pt-4">
        {loading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}
        {error && (
          <div className="py-8 text-center text-sm text-red-team">{error}</div>
        )}
        {!loading && !error && !hasAnyPieces && (
          <div className="py-16 text-center text-text-muted">
            No Pokémon yet. Start a game!
          </div>
        )}
        {!loading && !error && hasAnyPieces && (
          <div className="flex flex-col gap-6">
            <p className="text-center text-xs text-text-muted">
              Back rank: Squirtle · Charmander · Bulbasaur · Mew · King · Bulbasaur · Charmander · Squirtle
            </p>
            {redPieces.length > 0 && <SetRow pieces={redPieces} side="red" />}
            {bluePieces.length > 0 && <SetRow pieces={bluePieces} side="blue" />}
          </div>
        )}
      </div>
    </PageShell>
  );
}
