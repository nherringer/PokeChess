import React from "react";

interface XpBarProps {
  current: number;
  max: number;
  color?: string;
  className?: string;
}

export function XpBar({
  current,
  max,
  color = "#FFD700",
  className = "",
}: XpBarProps) {
  const fraction = Math.min(1, Math.max(0, max > 0 ? current / max : 0));
  const pct = Math.round(fraction * 100);

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
        className="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}
