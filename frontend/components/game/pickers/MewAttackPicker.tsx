"use client";

import React from "react";
import type { LegalMoveOut } from "@/lib/types/api";
import { DisambiguationSheet } from "./DisambiguationSheet";

interface MewAttackPickerProps {
  open: boolean;
  moves: LegalMoveOut[];
  onPick: (move: LegalMoveOut) => void;
  onClose: () => void;
}

const MOVE_SLOT_LABELS: Record<number, { emoji: string; name: string }> = {
  0: { emoji: "🌀", name: "Psychic" },
  1: { emoji: "🔮", name: "Foresight" },
  2: { emoji: "💥", name: "Shadow Ball" },
  3: { emoji: "⚡", name: "Thunder" },
};

export function MewAttackPicker({
  open,
  moves,
  onPick,
  onClose,
}: MewAttackPickerProps) {
  return (
    <DisambiguationSheet open={open} title="Choose Mew's attack:" onClose={onClose}>
      <div className="grid grid-cols-2 gap-2">
        {moves.map((move, i) => {
          const slot = move.move_slot ?? i;
          const info = MOVE_SLOT_LABELS[slot] ?? {
            emoji: "✨",
            name: move.action_type,
          };
          const isForesight = move.action_type === "FORESIGHT";
          return (
            <button
              key={i}
              onClick={() => onPick(move)}
              className={[
                "flex flex-col items-center justify-center p-3 rounded-xl font-bold text-white transition-all",
                "hover:scale-105 active:scale-95",
                isForesight
                  ? "bg-hl-foresight/20 border-2 border-hl-foresight"
                  : "bg-bg-card border-2 border-white/20 hover:border-white/50",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span style={{ fontSize: 24 }}>{info.emoji}</span>
              <span className="text-sm mt-1">{info.name}</span>
            </button>
          );
        })}
      </div>
    </DisambiguationSheet>
  );
}
