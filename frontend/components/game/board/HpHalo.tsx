import React from "react";
import { MAX_HP } from "@/lib/constants";

interface HpHaloProps {
  pieceType: string;
  currentHp: number;
}

export function HpHalo({ pieceType, currentHp }: HpHaloProps) {
  const maxHp = MAX_HP[pieceType] ?? 200;
  const fraction = Math.min(1, Math.max(0, maxHp > 0 ? currentHp / maxHp : 0));

  const size = 56;
  const strokeWidth = 4;
  const r = 26;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const dashArray = circumference * fraction;
  const dashOffset = 0;

  let color = "#4CAF50";
  if (fraction <= 0.25) color = "#EF4444";
  else if (fraction <= 0.5) color = "#FFD700";

  const isLow = fraction < 0.25;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="absolute inset-0 pointer-events-none"
      style={{ transform: "rotate(-90deg)" }}
    >
      {/* Background track */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.1)"
        strokeWidth={strokeWidth}
      />
      {/* HP arc */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={`${dashArray} ${circumference}`}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        className={isLow ? "animate-blink" : ""}
      />
    </svg>
  );
}
