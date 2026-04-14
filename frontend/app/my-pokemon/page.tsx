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
}

function RankCell({ piece, fileLabel, sameSpeCount, pieceIndex }: RankCellProps) {
  const sk = piece.species.toUpperCase();
  const emoji = PIECE_TYPE_EMOJIS[sk] ?? "?";
  const label = PIECE_TYPE_LABELS[sk] ?? piece.species;
  const type = POKEMON_TYPE_FOR_PIECE[sk];
  const threshold = getXpThreshold(piece.evolution_stage);

  return (
    <div className="flex w-[4.5rem] shrink-0 flex-col items-center gap-1">
      <span className="text-[10px] font-mono text-text-muted/80">{fileLabel}</span>
      <div className="w-full rounded-lg border border-white/10 bg-bg-deep/80 px-1.5 py-2 flex flex-col items-center">
        <PokemonSpriteAvatar
          speciesOrPieceType={piece.species}
          emojiFallback={emoji}
          sizePx={56}
          className="border-2 border-poke-blue"
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

/** e-file: Red king (Pikachu) vs Blue king (Eevee); XP follows your stored king row. */
function KingsRankCell({
  kingPiece,
  fileLabel,
  sameSpeCount,
  pieceIndex,
}: {
  kingPiece: PieceOut;
  fileLabel: string;
  sameSpeCount: number;
  pieceIndex: number;
}) {
  const sk = kingPiece.species.toUpperCase();
  const threshold = getXpThreshold(kingPiece.evolution_stage);
  const storedLabel = PIECE_TYPE_LABELS[sk] ?? kingPiece.species;

  return (
    <div className="flex w-[8.5rem] shrink-0 flex-col items-center gap-1">
      <span className="text-[10px] font-mono text-text-muted/80">{fileLabel}</span>
      <div className="w-full rounded-lg border border-white/10 bg-bg-deep/80 px-1.5 py-2">
        <p className="mb-1.5 text-center text-[10px] font-bold uppercase tracking-wide text-text-muted">
          Kings
        </p>
        <div className="flex items-start justify-center gap-2">
          <div className="flex flex-col items-center">
            <PokemonSpriteAvatar
              speciesOrPieceType="PIKACHU"
              emojiFallback={PIECE_TYPE_EMOJIS.PIKACHU ?? "⚡"}
              sizePx={44}
              className="border-2 border-red-team"
            />
            <span className="mt-0.5 text-[9px] font-bold text-red-team">Red</span>
          </div>
          <div className="flex flex-col items-center">
            <PokemonSpriteAvatar
              speciesOrPieceType="EEVEE"
              emojiFallback={PIECE_TYPE_EMOJIS.EEVEE ?? "🌟"}
              sizePx={44}
              className="border-2 border-poke-blue"
            />
            <span className="mt-0.5 text-[9px] font-bold text-poke-blue">Blue</span>
          </div>
        </div>
        <p className="mt-2 text-[9px] leading-snug text-text-muted text-center px-0.5">
          In PvP you play as <span className="text-red-team font-semibold">Red (Pikachu)</span> or{" "}
          <span className="text-poke-blue font-semibold">Blue (Eevee)</span>. Your roster king row is{" "}
          <span className="text-white font-semibold">{storedLabel}</span>
          {sameSpeCount > 1 && <span className="text-white/35"> #{pieceIndex + 1}</span>}.
        </p>
        <div className="mt-2 w-full px-0.5">
          <div className="mb-0.5 flex justify-between text-[9px] text-text-muted">
            <span>XP</span>
            <span>
              {kingPiece.xp}/{threshold}
            </span>
          </div>
          <XpBar current={kingPiece.xp} max={threshold} color="#FFD700" className="h-1.5" />
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

  const speciesCounts = useMemo(
    () =>
      pieces.reduce<Record<string, number>>((acc, p) => {
        acc[p.species] = (acc[p.species] ?? 0) + 1;
        return acc;
      }, {}),
    [pieces]
  );

  const speciesSeen: Record<string, number> = {};
  const ordered = useMemo(() => orderBackRank(pieces), [pieces]);

  const pieceIndexes = ordered.map((p) => {
    const count = speciesSeen[p.species] ?? 0;
    speciesSeen[p.species] = count + 1;
    return count;
  });

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
        {!loading && !error && pieces.length === 0 && (
          <div className="py-16 text-center text-text-muted">
            No Pokémon yet. Start a game!
          </div>
        )}
        {!loading && !error && ordered.length > 0 && (
          <div>
            <p className="mb-3 text-center text-xs text-text-muted">
              Back rank: Squirtle · Charmander · Bulbasaur · Mew · Kings · Bulbasaur · Charmander · Squirtle
            </p>
            <div className="overflow-x-auto pb-2 [-webkit-overflow-scrolling:touch]">
              <div className="mx-auto flex w-min min-w-full justify-center gap-1.5 px-1 sm:gap-2">
                {ordered.map((piece, i) => {
                  const file = FILE_LABELS[i] ?? `${i + 1}`;
                  const isEFileKing = i === 4 && normRole(piece.role) === "king";
                  if (isEFileKing) {
                    return (
                      <KingsRankCell
                        key={piece.id}
                        kingPiece={piece}
                        fileLabel={file}
                        sameSpeCount={speciesCounts[piece.species] ?? 1}
                        pieceIndex={pieceIndexes[i]}
                      />
                    );
                  }
                  return (
                    <RankCell
                      key={piece.id}
                      piece={piece}
                      fileLabel={file}
                      sameSpeCount={speciesCounts[piece.species] ?? 1}
                      pieceIndex={pieceIndexes[i]}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
