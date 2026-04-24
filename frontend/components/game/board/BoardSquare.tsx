"use client";

import React from "react";
import Image from "next/image";
import type { BoardPieceData, FloorItemData } from "@/lib/types/api";
import type { HighlightType } from "@/lib/game/highlightUtils";
import { HIGHLIGHT_COLORS } from "@/lib/game/highlightUtils";
import { ITEM_EMOJIS } from "@/lib/constants";
import { PieceChip } from "./PieceChip";
import { ForesightGlow } from "./ForesightGlow";
import { SafetyballBadge } from "./SafetyballBadge";

interface BoardSquareProps {
  row: number;
  col: number;
  piece: BoardPieceData | null;
  highlight: HighlightType | null;
  isSelected: boolean;
  hasForesight: boolean;
  isUnexploredGrass: boolean;
  floorItem: FloorItemData | null;
  onClick: () => void;
}

function GrassChip() {
  return (
    <div className="relative flex aspect-square w-full max-w-[min(3.75rem,56px,14vmin)] items-center justify-center pointer-events-none">
      <div
        className="absolute inset-[5%] rounded-full bg-bg-card flex items-center justify-center border-2 overflow-hidden"
        style={{ borderColor: "#4b5563" }}
      >
        <Image
          src="/sprites/pokemon/tall_grass.jpeg"
          alt=""
          width={48}
          height={48}
          className="h-[96%] w-[96%] object-cover select-none pointer-events-none"
          unoptimized
        />
      </div>
    </div>
  );
}

export function BoardSquare({
  row,
  col,
  piece,
  highlight,
  isSelected,
  hasForesight,
  isUnexploredGrass,
  floorItem,
  onClick,
}: BoardSquareProps) {
  const isLight = (row + col) % 2 === 0;
  const baseBg = isLight ? "#EBF0CE" : "#6E8F52";

  const highlightColor = highlight ? HIGHLIGHT_COLORS[highlight] : null;

  return (
    <div
      className="relative min-h-0 min-w-0 h-full w-full flex items-center justify-center cursor-pointer select-none"
      style={{
        backgroundColor: baseBg,
        outline: isSelected ? "3px solid #64A0FF" : undefined,
        outlineOffset: "-2px",
      }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {/* Unexplored tall grass overlay — almost black */}
      {isUnexploredGrass && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ backgroundColor: "rgba(0,0,0,0.88)" }}
        />
      )}

      {/* Highlight overlay */}
      {highlightColor && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ backgroundColor: `${highlightColor}66` }}
        />
      )}

      {/* Foresight glow */}
      {hasForesight && <ForesightGlow />}

      {/* Grass chip: shown on unexplored empty squares */}
      {isUnexploredGrass && !piece && (
        <div className="relative z-10 flex h-full w-full min-h-0 min-w-0 items-center justify-center p-[5%] pointer-events-none">
          <GrassChip />
        </div>
      )}

      {/* Floor item on empty non-grass square */}
      {!piece && floorItem && !isUnexploredGrass && (
        <span
          className="relative z-10 pointer-events-none"
          style={{ fontSize: 18, opacity: 0.85 }}
          role="img"
          aria-label={floorItem.item}
        >
          {ITEM_EMOJIS[floorItem.item] ?? "❓"}
        </span>
      )}

      {/* Piece — wrapper fills the square so PieceChip % widths resolve to the cell */}
      {piece && (
        <div className="relative z-10 flex h-full w-full min-h-0 min-w-0 items-center justify-center p-[5%] pointer-events-none">
          <PieceChip piece={piece} isSelected={isSelected} />
          {/* Safetyball stored piece badge */}
          {(piece.piece_type === "SAFETYBALL" ||
            piece.piece_type === "MASTER_SAFETYBALL") &&
            piece.stored_piece && (
              <SafetyballBadge storedPiece={piece.stored_piece} />
            )}
        </div>
      )}

      {/* Dot indicator for empty highlighted squares — hidden when grass chip shows */}
      {!piece && !floorItem && !isUnexploredGrass && highlight && highlight !== "select" && (
        <div
          className="w-3 h-3 rounded-full opacity-80 pointer-events-none"
          style={{ backgroundColor: highlightColor ?? undefined }}
        />
      )}
    </div>
  );
}
