import React from "react";

interface HpBarProps {
  current: number;
  max: number;
  className?: string;
  color?: string;
}

export function HpBar({ current, max, className = "", color }: HpBarProps) {
  const fraction = Math.min(1, Math.max(0, max > 0 ? current / max : 0));
  const pct = Math.round(fraction * 100);

  let barColor = color;
  if (!barColor) {
    if (fraction > 0.5) barColor = "#4CAF50";
    else if (fraction > 0.25) barColor = "#FFD700";
    else barColor = "#EF4444";
  }

  return (
    <div
      className={[
        "relative h-2 bg-white/10 rounded-full overflow-hidden",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        className="absolute left-0 top-0 h-full rounded-full transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: barColor }}
      />
    </div>
  );
}
