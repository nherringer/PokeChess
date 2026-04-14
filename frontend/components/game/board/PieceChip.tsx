import React from "react";
import Image from "next/image";
import type { BoardPieceData } from "@/lib/types/api";
import { PIECE_TYPE_EMOJIS } from "@/lib/constants";
import { pokemonSpriteSrc } from "@/lib/game/pokemonSprites";
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
  const sprite = pokemonSpriteSrc(piece.piece_type);

  return (
    <div className="relative flex aspect-square w-[min(78%,3.75rem)] max-w-[min(56px,12vmin)] items-center justify-center">
      <HpHalo pieceType={piece.piece_type} currentHp={piece.current_hp} />

      <div
        className="absolute inset-[5%] rounded-full bg-bg-card flex items-center justify-center border-2 transition-all duration-100 overflow-hidden"
        style={{
          borderColor: isSelected ? "#64A0FF" : borderColor,
          boxShadow: isSelected
            ? `0 0 0 2px #64A0FF`
            : `0 0 0 1px ${borderColor}44`,
        }}
      >
        {sprite ? (
          <Image
            src={sprite}
            alt=""
            width={48}
            height={48}
            className="h-[96%] w-[96%] object-contain select-none pointer-events-none"
            unoptimized
          />
        ) : (
          <span
            className="text-[clamp(0.65rem,3.5vmin,1.15rem)] leading-none select-none"
            role="img"
            aria-label={piece.piece_type}
          >
            {emoji}
          </span>
        )}
      </div>
    </div>
  );
}
