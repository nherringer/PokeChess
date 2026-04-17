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

const MEW_ATTACK_SLOTS: Record<number, { emoji: string; name: string }> = {
  0: { emoji: "🔥", name: "Fire Blast" },
  1: { emoji: "💧", name: "Hydro Pump" },
  2: { emoji: "☀️", name: "Solar Beam" },
};

type MewMoveDisplayInfo = { emoji: string; name: string; subtitle?: string };

/** Display order for Mew's three typed attacks (engine slots 0/1/2). */
const MEW_SLOT_DISPLAY_ORDER: number[] = [1, 2, 0];

function mewMoveDisplay(
  move: LegalMoveOut,
  allMoves: LegalMoveOut[]
): MewMoveDisplayInfo {
  const attackBranches = allMoves.filter((m) => m.action_type === "ATTACK");

  switch (move.action_type) {
    case "MOVE":
      return { emoji: "➡️", name: "Move", subtitle: "Reposition" };
    case "FORESIGHT":
      return {
        emoji: "🔮",
        name: "Foresight",
        subtitle: "Attack — damage next turn",
      };
    case "ATTACK": {
      const slot = move.move_slot;
      if (slot === null || slot === undefined) {
        return { emoji: "✨", name: "Attack" };
      }
      // Mew vs stealball: engine emits a single ATTACK (slot 0); not a typed matchup.
      if (
        attackBranches.length === 1 &&
        slot === 0 &&
        !attackBranches.some((m) => m.move_slot === 1)
      ) {
        return { emoji: "⚪", name: "Capture", subtitle: "Into Poké Ball" };
      }
      return (
        MEW_ATTACK_SLOTS[slot] ?? { emoji: "✨", name: `Attack (${slot})` }
      );
    }
    default:
      return { emoji: "✨", name: move.action_type };
  }
}

/**
 * Open square: Move, then Foresight.
 * Enemy Pokémon: Foresight, then Hydro Pump → Solar Beam → Fire Blast.
 * Other (e.g. Espeon): Foresight then direct Attack.
 */
function sortMewPickerMoves(moves: LegalMoveOut[]): LegalMoveOut[] {
  const attackBranches = moves.filter((m) => m.action_type === "ATTACK");
  const mewThreeSlot =
    attackBranches.length >= 2 &&
    attackBranches.some((m) => m.move_slot === 1) &&
    attackBranches.some((m) => m.move_slot === 2);

  const rank = (m: LegalMoveOut): number => {
    if (m.action_type === "MOVE") return 0;
    if (m.action_type === "FORESIGHT") return 1;
    if (m.action_type === "ATTACK") {
      if (mewThreeSlot && m.move_slot != null) {
        const idx = MEW_SLOT_DISPLAY_ORDER.indexOf(m.move_slot);
        return 2 + (idx >= 0 ? idx : m.move_slot);
      }
      return 2;
    }
    return 20;
  };
  return [...moves].sort((a, b) => rank(a) - rank(b));
}

function pickerTitle(moves: LegalMoveOut[]): string {
  const hasReposition = moves.some((m) => m.action_type === "MOVE");
  return hasReposition ? "Move or Foresight" : "Choose attack";
}

export function MewAttackPicker({
  open,
  moves,
  onPick,
  onClose,
}: MewAttackPickerProps) {
  const orderedMoves = sortMewPickerMoves(moves);
  const title = pickerTitle(moves);

  return (
    <DisambiguationSheet open={open} title={title} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2">
        {orderedMoves.map((move, i) => {
          const info = mewMoveDisplay(move, moves);
          const isForesight = move.action_type === "FORESIGHT";
          const isImmediateAttack = move.action_type === "ATTACK";
          return (
            <button
              key={i}
              onClick={() => onPick(move)}
              className={[
                "flex flex-col items-center justify-center p-3 rounded-xl font-bold text-white transition-all",
                "hover:scale-105 active:scale-95",
                isForesight
                  ? "bg-hl-foresight/20 border-2 border-hl-foresight"
                  : isImmediateAttack
                    ? "bg-hl-attack/15 border-2 border-hl-attack/60"
                    : "bg-bg-card border-2 border-white/20 hover:border-white/50",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span style={{ fontSize: 24 }}>{info.emoji}</span>
              <span className="text-sm mt-1 text-center leading-tight">{info.name}</span>
              {info.subtitle ? (
                <span className="text-[11px] font-normal text-white/75 mt-1 text-center leading-snug px-1">
                  {info.subtitle}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </DisambiguationSheet>
  );
}
