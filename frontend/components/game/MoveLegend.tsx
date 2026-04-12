import React from "react";
import { HIGHLIGHT_COLORS } from "@/lib/game/highlightUtils";

const LEGEND_ITEMS = [
  { type: "move", label: "Move" },
  { type: "attack", label: "Attack" },
  { type: "foresight", label: "Foresight" },
  { type: "trade", label: "Trade" },
  { type: "evolve", label: "Evolve" },
] as const;

export function MoveLegend() {
  return (
    <div className="mt-3 bg-bg-card rounded-xl p-3">
      <p className="text-xs font-bold text-white/50 uppercase tracking-wide mb-2">
        Legend
      </p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {LEGEND_ITEMS.map(({ type, label }) => (
          <div key={type} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: HIGHLIGHT_COLORS[type] }}
            />
            <span className="text-xs text-white/70">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
