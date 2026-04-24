"use client";

import React from "react";
import type { LegalMoveOut } from "@/lib/types/api";
import { DisambiguationSheet } from "./DisambiguationSheet";
import { Button } from "@/components/ui/Button";

const ATTACK_LABELS: Record<string, string> = {
  LEAFEON:  "🌿 Solarbeam",
  VAPOREON: "💧 Water Gun",
  FLAREON:  "🔥 Flare Blitz",
  JOLTEON:  "⚡ Thunder",
  EEVEE:    "⭐ Attack",
};

interface AttackOrQAPickerProps {
  open: boolean;
  moves: LegalMoveOut[];
  pieceType: string;
  onPickAttack: (move: LegalMoveOut) => void;
  onPickQA: (move: LegalMoveOut) => void;
  onClose: () => void;
}

export function AttackOrQAPicker({
  open,
  moves,
  pieceType,
  onPickAttack,
  onPickQA,
  onClose,
}: AttackOrQAPickerProps) {
  const attackMove = moves.find((m) => m.action_type === "ATTACK") ?? null;
  const qaMove = moves.find((m) => m.action_type === "QUICK_ATTACK") ?? null;
  const attackLabel = ATTACK_LABELS[pieceType] ?? "Attack";

  return (
    <DisambiguationSheet open={open} title="Choose attack type" onClose={onClose}>
      <div className="flex flex-col gap-3">
        {attackMove && (
          <Button variant="primary" size="lg" fullWidth onClick={() => onPickAttack(attackMove)}>
            {attackLabel}
          </Button>
        )}
        {qaMove && (
          <Button variant="secondary" size="lg" fullWidth onClick={() => onPickQA(qaMove)}>
            ⚡ Quick Attack
          </Button>
        )}
      </div>
    </DisambiguationSheet>
  );
}
