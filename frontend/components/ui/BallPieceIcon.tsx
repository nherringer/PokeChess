"use client";

import React, { useId } from "react";

/**
 * Ball visuals match `pokechess_ui.py` `_draw_ball` / `_draw_chip_ball`:
 * - Stealball (POKEBALL / MASTERBALL): red or purple top, black bottom
 * - Safety / "heal" (SAFETYBALL / MASTER_SAFETYBALL): red or purple top, white bottom — classic Pokéball-style
 */
export type BallPieceVariant = "steal" | "steal_master" | "safety" | "safety_master";

const VARIANT_COLORS: Record<
  BallPieceVariant,
  { top: string; bottom: string; mFill: string }
> = {
  steal: {
    top: "rgb(200, 50, 50)",
    bottom: "rgb(30, 30, 30)",
    mFill: "rgb(240, 240, 255)",
  },
  steal_master: {
    top: "rgb(128, 0, 180)",
    bottom: "rgb(30, 30, 30)",
    mFill: "rgb(240, 240, 255)",
  },
  safety: {
    top: "rgb(200, 50, 50)",
    bottom: "rgb(240, 240, 240)",
    mFill: "rgb(240, 240, 255)",
  },
  safety_master: {
    top: "rgb(128, 0, 180)",
    bottom: "rgb(240, 240, 240)",
    mFill: "rgb(240, 240, 255)",
  },
};

const LINE = "rgb(20, 20, 20)";

export function ballPieceVariantFromType(
  pieceType: string
): BallPieceVariant | null {
  switch (pieceType.trim().toUpperCase()) {
    case "POKEBALL":
      return "steal";
    case "MASTERBALL":
      return "steal_master";
    case "SAFETYBALL":
      return "safety";
    case "MASTER_SAFETYBALL":
      return "safety_master";
    default:
      return null;
  }
}

interface BallPieceIconProps {
  variant: BallPieceVariant;
  className?: string;
}

export function BallPieceIcon({ variant, className }: BallPieceIconProps) {
  const { top, bottom, mFill } = VARIANT_COLORS[variant];
  const showM = variant === "steal_master" || variant === "safety_master";
  const clipId = `ball-clip-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;

  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      aria-hidden
    >
      <defs>
        <clipPath id={clipId}>
          <rect x="0" y="0" width="100" height="50" />
        </clipPath>
      </defs>
      {/* Full disk (bottom half color); top will be covered */}
      <circle cx="50" cy="50" r="48" fill={bottom} />
      {/* Upper semicircle in top color */}
      <circle
        cx="50"
        cy="50"
        r="48"
        fill={top}
        style={{ clipPath: `url(#${clipId})` }}
      />
      <circle
        cx="50"
        cy="50"
        r="48"
        fill="none"
        stroke={LINE}
        strokeWidth="2"
      />
      <line x1="2" y1="50" x2="98" y2="50" stroke={LINE} strokeWidth="2" />
      <circle
        cx="50"
        cy="50"
        r="10"
        fill={bottom}
        stroke={LINE}
        strokeWidth="2"
      />
      {showM && (
        <text
          x="50"
          y="36"
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fontSize: 20,
            fontWeight: 700,
            fontFamily: "system-ui, sans-serif",
            fill: mFill,
          }}
        >
          M
        </text>
      )}
    </svg>
  );
}
