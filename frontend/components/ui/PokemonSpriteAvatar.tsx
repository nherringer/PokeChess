"use client";

import type { CSSProperties } from "react";
import Image from "next/image";
import { pokemonSpriteSrc } from "@/lib/game/pokemonSprites";
import {
  BallPieceIcon,
  ballPieceVariantFromType,
} from "@/components/ui/BallPieceIcon";

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
  const ballVariant = ballPieceVariantFromType(speciesOrPieceType);

  return (
    <div
      className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-bg-panel ${className}`}
      style={{ width: sizePx, height: sizePx, ...style }}
    >
      {ballVariant ? (
        <BallPieceIcon
          variant={ballVariant}
          className="h-[90%] w-[90%]"
        />
      ) : src ? (
        <Image
          src={src}
          alt=""
          width={sizePx}
          height={sizePx}
          className="h-[96%] w-[96%] object-contain"
          unoptimized
        />
      ) : (
        <span style={{ fontSize: Math.round(sizePx * 0.45) }}>{emojiFallback}</span>
      )}
    </div>
  );
}
