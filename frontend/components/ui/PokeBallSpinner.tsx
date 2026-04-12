import React from "react";

interface PokeBallSpinnerProps {
  size?: number;
  className?: string;
}

export function PokeBallSpinner({
  size = 32,
  className = "",
}: PokeBallSpinnerProps) {
  return (
    <span
      className={["inline-block animate-spin", className]
        .filter(Boolean)
        .join(" ")}
      style={{ fontSize: size, lineHeight: 1, display: "inline-block" }}
    >
      ⚪
    </span>
  );
}
