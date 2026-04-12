import React from "react";
import type { MoveHistoryEntry } from "@/lib/types/api";
import { getLastMoveText } from "@/lib/game/lastMoveText";

interface LastMoveLogProps {
  entry: MoveHistoryEntry | undefined;
}

export function LastMoveLog({ entry }: LastMoveLogProps) {
  const text = getLastMoveText(entry);
  if (!text) return null;

  const result = entry?.result ?? {};
  const multiplier = result.type_multiplier as number | null;

  let textColor = "text-white";
  if (multiplier && multiplier >= 2) textColor = "text-hl-attack";
  else if (multiplier && multiplier <= 0.5) textColor = "text-white/50";

  return (
    <div className={["text-sm font-bold", textColor].filter(Boolean).join(" ")}>
      {text}
    </div>
  );
}
