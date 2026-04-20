import React from "react";
import type { BoardPieceData } from "@/lib/types/api";
import { PIECE_TYPE_EMOJIS, ITEM_EMOJIS } from "@/lib/constants";
import { HpHalo } from "./HpHalo";

interface PieceChipProps {
  piece: BoardPieceData;
  isSelected?: boolean;
}

const TEAM_COLORS = {
  RED: "#E03737",
  BLUE: "#3C72E0",
};

export function PieceChip({ piece, isSelected = false }: PieceChipProps) {
  const emoji = PIECE_TYPE_EMOJIS[piece.piece_type] ?? "?";
  const borderColor = TEAM_COLORS[piece.team];
  const itemEmoji = piece.held_item && piece.held_item !== "NONE"
    ? (ITEM_EMOJIS[piece.held_item] ?? "❓")
    : null;

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: 56, height: 56 }}
    >
      {/* HP Halo SVG */}
      <HpHalo pieceType={piece.piece_type} currentHp={piece.current_hp} />

      {/* Inner circle */}
      <div
        className="absolute inset-1.5 rounded-full bg-bg-card flex items-center justify-center border-2 transition-all duration-100"
        style={{
          borderColor: isSelected ? "#64A0FF" : borderColor,
          boxShadow: isSelected
            ? `0 0 0 2px #64A0FF`
            : `0 0 0 1px ${borderColor}44`,
        }}
      >
        <span
          style={{ fontSize: 20, lineHeight: 1, userSelect: "none" }}
          role="img"
          aria-label={piece.piece_type}
        >
          {emoji}
        </span>
      </div>

      {/* Held item badge */}
      {itemEmoji && (
        <div
          className="absolute bottom-0 right-0 rounded-full bg-bg-deep flex items-center justify-center"
          style={{ width: 16, height: 16, fontSize: 10 }}
        >
          {itemEmoji}
        </div>
      )}
    </div>
  );
}
