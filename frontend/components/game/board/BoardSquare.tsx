"use client";

import React from "react";
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
      className="relative aspect-square flex items-center justify-center cursor-pointer select-none"
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
      {/* Unexplored tall grass overlay */}
      {isUnexploredGrass && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
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

      {/* Floor item on empty square */}
      {!piece && floorItem && (
        <span
          className="relative z-10 pointer-events-none"
          style={{ fontSize: 18, opacity: 0.85 }}
          role="img"
          aria-label={floorItem.item}
        >
          {ITEM_EMOJIS[floorItem.item] ?? "❓"}
        </span>
      )}

      {/* Piece */}
      {piece && (
        <div className="relative z-10">
          <PieceChip piece={piece} isSelected={isSelected} />
          {/* Safetyball stored piece badge */}
          {(piece.piece_type === "SAFETYBALL" ||
            piece.piece_type === "MASTER_SAFETYBALL") &&
            piece.stored_piece && (
              <SafetyballBadge storedPiece={piece.stored_piece} />
            )}
        </div>
      )}

      {/* Dot indicator for empty highlight squares */}
      {!piece && !floorItem && highlight && highlight !== "select" && (
        <div
          className="w-3 h-3 rounded-full opacity-80 pointer-events-none"
          style={{ backgroundColor: highlightColor ?? undefined }}
        />
      )}
    </div>
  );
}
