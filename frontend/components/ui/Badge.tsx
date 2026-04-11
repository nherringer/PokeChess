import React from "react";
import { POKEMON_TYPE_COLORS } from "@/lib/constants";

interface BadgeProps {
  type: string;
  className?: string;
}

export function Badge({ type, className = "" }: BadgeProps) {
  const color = POKEMON_TYPE_COLORS[type.toUpperCase()] ?? "#BDBDBD";
  const label = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();

  return (
    <span
      className={[
        "inline-block px-2 py-0.5 rounded-full text-xs font-bold text-black",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ backgroundColor: color }}
    >
      {label}
    </span>
  );
}
