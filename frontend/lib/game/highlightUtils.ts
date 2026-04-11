import type { LegalMoveOut } from "@/lib/types/api";
import { apiToDisplay } from "./boardUtils";

export type HighlightType =
  | "select"
  | "move"
  | "attack"
  | "foresight"
  | "trade"
  | "evolve"
  | "release"
  | "pokeball"
  | "masterball";

export function actionTypeToHighlight(actionType: string): HighlightType {
  switch (actionType) {
    case "MOVE":
      return "move";
    case "ATTACK":
      return "attack";
    case "QUICK_ATTACK":
      return "attack";
    case "POKEBALL_ATTACK":
      return "pokeball";
    case "MASTERBALL_ATTACK":
      return "masterball";
    case "FORESIGHT":
      return "foresight";
    case "TRADE":
      return "trade";
    case "EVOLVE":
      return "evolve";
    case "RELEASE":
      return "release";
    default:
      return "move";
  }
}

export const HIGHLIGHT_COLORS: Record<HighlightType, string> = {
  select: "#64A0FF",
  move: "#F5E028",
  attack: "#F55A19",
  foresight: "#32D7FA",
  trade: "#A855F7",
  evolve: "#FFD700",
  release: "#4CAF50",
  pokeball: "#F55A19",
  masterball: "#6B21A8",
};

export function buildHighlightMap(
  legalMoves: LegalMoveOut[],
  selectedSquare: { row: number; col: number } | null,
  localSide: "red" | "blue",
  quickAttackStep?: 0 | 1,
  quickAttackTarget?: { row: number; col: number } | null
): Map<string, HighlightType> {
  const map = new Map<string, HighlightType>();

  if (!selectedSquare) return map;

  // Add selection highlight for the selected square itself
  map.set(`${selectedSquare.row},${selectedSquare.col}`, "select");

  for (const move of legalMoves) {
    // In quick attack step 1, only show QUICK_ATTACK moves where secondary matches
    if (quickAttackStep === 1 && quickAttackTarget) {
      if (move.action_type !== "QUICK_ATTACK") continue;
      const apiTarget = {
        row: quickAttackTarget.row,
        col: quickAttackTarget.col,
      };
      // The secondary row/col is the move destination after attacking
      // Filter to only moves that attacked our stored target
      const { row: displayPieceRow } = apiToDisplay(
        move.piece_row,
        move.piece_col,
        localSide
      );
      const { row: displayTargetRow } = apiToDisplay(
        move.target_row,
        move.target_col,
        localSide
      );
      if (
        displayPieceRow !== selectedSquare.row ||
        displayTargetRow !== apiTarget.row ||
        move.target_col !== apiTarget.col
      ) {
        continue;
      }
    }

    const { row: displayRow, col } = apiToDisplay(
      move.target_row,
      move.target_col,
      localSide
    );
    const key = `${displayRow},${col}`;
    const highlight = actionTypeToHighlight(move.action_type);

    // Don't overwrite attack highlights with less important ones
    if (!map.has(key)) {
      map.set(key, highlight);
    }
  }

  return map;
}
