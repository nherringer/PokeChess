"use client";

import React from "react";
import type { BoardPieceData } from "@/lib/types/api";
import type { HighlightType } from "@/lib/game/highlightUtils";
import { HIGHLIGHT_COLORS } from "@/lib/game/highlightUtils";
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
  onClick: () => void;
}

export function BoardSquare({
  row,
  col,
  piece,
  highlight,
  isSelected,
  hasForesight,
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
      {/* Highlight overlay */}
      {highlightColor && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ backgroundColor: `${highlightColor}66` }}
        />
      )}

      {/* Foresight glow */}
      {hasForesight && <ForesightGlow />}

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
      {!piece && highlight && highlight !== "select" && (
        <div
          className="w-3 h-3 rounded-full opacity-80 pointer-events-none"
          style={{ backgroundColor: highlightColor ?? undefined }}
        />
      )}
    </div>
  );
}
