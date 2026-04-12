"use client";

import React from "react";
import type { LegalMoveOut } from "@/lib/types/api";
import { DisambiguationSheet } from "./DisambiguationSheet";
import { EvolveSparkle } from "./EvolveSparkle";
import { EEVEE_EVOLUTIONS } from "@/lib/constants";

interface EeveeEvolvePickerProps {
  open: boolean;
  moves: LegalMoveOut[];
  onPick: (move: LegalMoveOut) => void;
  onClose: () => void;
}

export function EeveeEvolvePicker({
  open,
  moves,
  onPick,
  onClose,
}: EeveeEvolvePickerProps) {
  return (
    <DisambiguationSheet
      open={open}
      title="What will Eevee evolve into?"
      onClose={onClose}
    >
      <div
        className="rounded-xl border-2 p-3"
        style={{ borderColor: "#FFD700" }}
      >
        <div className="grid grid-cols-5 gap-2">
          {EEVEE_EVOLUTIONS.map((evo) => {
            const move = moves.find((m) => m.move_slot === evo.slot);
            if (!move) return null;
            return (
              <EvolveSparkle key={evo.slot}>
                <button
                  onClick={() => onPick(move)}
                  className="flex flex-col items-center p-2 rounded-lg bg-bg-card hover:bg-white/10 transition-all w-full"
                >
                  <span style={{ fontSize: 24 }}>{evo.emoji}</span>
                  <span className="text-xs text-white/80 mt-1 font-bold leading-tight text-center">
                    {evo.name}
                  </span>
                </button>
              </EvolveSparkle>
            );
          })}
        </div>
      </div>
    </DisambiguationSheet>
  );
}
