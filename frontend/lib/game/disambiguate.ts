import type { LegalMoveOut } from "@/lib/types/api";

export type PickerType = "mew_attack" | "pikachu_evolve" | "eevee_evolve" | "item_overflow" | "attack_or_qa";

export function detectDisambiguation(
  legalMoves: LegalMoveOut[],
  targetRow: number,
  targetCol: number
): LegalMoveOut[] | null {
  const movesToTarget = legalMoves.filter(
    (m) => m.target_row === targetRow && m.target_col === targetCol
  );

  if (movesToTarget.length <= 1) return null;

  // When both ATTACK and QUICK_ATTACK go to the same square (e.g. Leafeon diagonal),
  // collapse QA variants to one representative — the player just needs to choose the type.
  const attackMoves = movesToTarget.filter((m) => m.action_type === "ATTACK");
  const qaMoves = movesToTarget.filter((m) => m.action_type === "QUICK_ATTACK");
  if (attackMoves.length > 0 && qaMoves.length > 0) {
    return [...attackMoves, qaMoves[0]];
  }

  return movesToTarget;
}

export function classifyPicker(moves: LegalMoveOut[]): PickerType {
  // Attack vs Quick Attack disambiguation
  const hasQA = moves.some((m) => m.action_type === "QUICK_ATTACK");
  const hasAttack = moves.some((m) => m.action_type === "ATTACK");
  if (hasQA && hasAttack) return "attack_or_qa";

  // Item overflow: moves differ only by overflow_keep
  const overflowMoves = moves.filter((m) => m.overflow_keep !== null && m.overflow_keep !== undefined);
  if (overflowMoves.length > 0) {
    const keepValues = new Set(overflowMoves.map((m) => m.overflow_keep));
    if (keepValues.size > 1) return "item_overflow";
  }

  // If any move is EVOLVE, check what kind
  // Eevee EVOLVE moves always carry a move_slot (the stone used); Pikachu's don't.
  const evolveMoves = moves.filter((m) => m.action_type === "EVOLVE");
  if (evolveMoves.length > 0) {
    const hasSlot = evolveMoves.some((m) => m.move_slot !== null && m.move_slot !== undefined);
    if (hasSlot) return "eevee_evolve";
    return "pikachu_evolve";
  }

  // If move_slot varies for ATTACK/FORESIGHT → mew_attack
  const attackMoves2 = moves.filter(
    (m) => m.action_type === "ATTACK" || m.action_type === "FORESIGHT"
  );
  if (attackMoves2.length > 0) {
    const slots = new Set(attackMoves2.map((m) => m.move_slot));
    if (slots.size > 1) return "mew_attack";
  }

  return "mew_attack";
}
