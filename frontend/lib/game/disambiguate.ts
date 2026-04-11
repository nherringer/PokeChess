import type { LegalMoveOut } from "@/lib/types/api";

export type PickerType = "mew_attack" | "pikachu_evolve" | "eevee_evolve";

export function detectDisambiguation(
  legalMoves: LegalMoveOut[],
  targetRow: number,
  targetCol: number
): LegalMoveOut[] | null {
  const movesToTarget = legalMoves.filter(
    (m) => m.target_row === targetRow && m.target_col === targetCol
  );

  if (movesToTarget.length <= 1) return null;

  // Multiple moves to the same target — disambiguation needed
  return movesToTarget;
}

export function classifyPicker(moves: LegalMoveOut[]): PickerType {
  // If any move is EVOLVE, check what kind
  const evolveMoves = moves.filter((m) => m.action_type === "EVOLVE");
  if (evolveMoves.length > 0) {
    // If multiple evolve moves with different slots → eevee_evolve
    if (evolveMoves.length > 1) return "eevee_evolve";
    // Single evolve → pikachu evolve
    return "pikachu_evolve";
  }

  // If move_slot varies for ATTACK/FORESIGHT → mew_attack
  const attackMoves = moves.filter(
    (m) => m.action_type === "ATTACK" || m.action_type === "FORESIGHT"
  );
  if (attackMoves.length > 0) {
    const slots = new Set(attackMoves.map((m) => m.move_slot));
    if (slots.size > 1) return "mew_attack";
  }

  return "mew_attack";
}
