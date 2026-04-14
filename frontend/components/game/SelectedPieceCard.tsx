import React from "react";
import type { BoardPieceData } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { HpBar } from "@/components/ui/HpBar";
import {
  PIECE_TYPE_EMOJIS,
  PIECE_TYPE_LABELS,
  POKEMON_TYPE_FOR_PIECE,
  MAX_HP,
} from "@/lib/constants";
import { PokemonSpriteAvatar } from "@/components/ui/PokemonSpriteAvatar";

interface SelectedPieceCardProps {
  piece: BoardPieceData;
  index?: number;
  className?: string;
}

export function SelectedPieceCard({
  piece,
  index = 0,
  className = "",
}: SelectedPieceCardProps) {
  const emoji = PIECE_TYPE_EMOJIS[piece.piece_type] ?? "?";
  const label = PIECE_TYPE_LABELS[piece.piece_type] ?? piece.piece_type;
  const type = POKEMON_TYPE_FOR_PIECE[piece.piece_type];
  const maxHp = MAX_HP[piece.piece_type] ?? 200;
  const teamColor = piece.team === "RED" ? "#E03737" : "#3C72E0";

  return (
    <div
      className={[
        "bg-bg-card rounded-xl p-3 flex items-start gap-3",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Avatar */}
      <PokemonSpriteAvatar
        speciesOrPieceType={piece.piece_type}
        emojiFallback={emoji}
        sizePx={56}
        className="border-2"
        style={{ borderColor: teamColor }}
      />

      {/* Details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-display font-bold text-white text-base">
            {label}
            {index > 0 && (
              <span className="text-white/40 text-sm"> #{index + 1}</span>
            )}
          </span>
          {type && <Badge type={type} />}
        </div>

        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-white/50 w-6">HP</span>
          <HpBar current={piece.current_hp} max={maxHp} className="flex-1" />
          <span className="text-xs text-white/50 w-16 text-right">
            {piece.current_hp}/{maxHp}
          </span>
        </div>

        {piece.held_item && piece.held_item !== "NONE" && (
          <div className="mt-1 text-xs text-white/50">
            Held: {piece.held_item}
          </div>
        )}
      </div>
    </div>
  );
}
