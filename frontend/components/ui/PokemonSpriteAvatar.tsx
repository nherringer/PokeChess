"use client";

import type { CSSProperties } from "react";
import Image from "next/image";
import { pokemonSpriteSrc } from "@/lib/game/pokemonSprites";

interface PokemonSpriteAvatarProps {
  speciesOrPieceType: string;
  emojiFallback: string;
  sizePx: number;
  className?: string;
  style?: CSSProperties;
}

/** Rounded avatar: local dex sprite when available, else emoji (e.g. pokéballs). */
export function PokemonSpriteAvatar({
  speciesOrPieceType,
  emojiFallback,
  sizePx,
  className = "",
  style,
}: PokemonSpriteAvatarProps) {
  const src = pokemonSpriteSrc(speciesOrPieceType);

  return (
    <div
      className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-bg-panel ${className}`}
      style={{ width: sizePx, height: sizePx, ...style }}
    >
      {src ? (
        <Image
          src={src}
          alt=""
          width={sizePx}
          height={sizePx}
          className="h-[88%] w-[88%] object-contain"
          unoptimized
        />
      ) : (
        <span style={{ fontSize: Math.round(sizePx * 0.45) }}>{emojiFallback}</span>
      )}
    </div>
  );
}
