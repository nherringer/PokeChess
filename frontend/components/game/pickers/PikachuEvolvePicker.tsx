"use client";

import React from "react";
import type { LegalMoveOut } from "@/lib/types/api";
import { DisambiguationSheet } from "./DisambiguationSheet";
import { Button } from "@/components/ui/Button";

interface PikachuEvolvePickerProps {
  open: boolean;
  move: LegalMoveOut | null;
  onConfirm: (move: LegalMoveOut) => void;
  onClose: () => void;
}

export function PikachuEvolvePicker({
  open,
  move,
  onConfirm,
  onClose,
}: PikachuEvolvePickerProps) {
  return (
    <DisambiguationSheet
      open={open}
      title="Pikachu wants to evolve!"
      onClose={onClose}
    >
      <div className="flex flex-col items-center gap-4">
        <div className="text-5xl animate-bounce-scale">⚡</div>
        <p className="text-white/70 text-sm text-center">
          Pikachu will evolve into Raichu. This costs your turn!
        </p>
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={() => move && onConfirm(move)}
        >
          ⚡ Evolve into Raichu
        </Button>
      </div>
    </DisambiguationSheet>
  );
}
