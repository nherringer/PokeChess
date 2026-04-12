import React from "react";
import { PIECE_TYPE_EMOJIS } from "@/lib/constants";
import type { BoardPieceData } from "@/lib/types/api";

interface SafetyballBadgeProps {
  storedPiece: BoardPieceData;
}

export function SafetyballBadge({ storedPiece }: SafetyballBadgeProps) {
  const emoji = PIECE_TYPE_EMOJIS[storedPiece.piece_type] ?? "?";
  return (
    <div
      className="absolute bottom-0 right-0 w-4 h-4 rounded-full bg-bg-panel flex items-center justify-center border border-white/30"
      style={{ fontSize: 9 }}
    >
      {emoji}
    </div>
  );
}
