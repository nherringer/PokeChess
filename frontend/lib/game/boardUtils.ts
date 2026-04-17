import type { GameStateData, BoardPieceData } from "@/lib/types/api";

export function flipRow(row: number, localSide: "red" | "blue"): number {
  return localSide === "red" ? 7 - row : row;
}

export function apiToDisplay(
  row: number,
  col: number,
  localSide: "red" | "blue"
): { row: number; col: number } {
  return { row: flipRow(row, localSide), col };
}

export function displayToApi(
  row: number,
  col: number,
  localSide: "red" | "blue"
): { row: number; col: number } {
  return { row: flipRow(row, localSide), col };
}

export function parseBoardGrid(
  state: GameStateData,
  localSide: "red" | "blue"
): (BoardPieceData | null)[][] {
  const grid: (BoardPieceData | null)[][] = Array.from({ length: 8 }, () =>
    Array(8).fill(null)
  );

  for (const piece of state.board) {
    const { row: displayRow, col } = apiToDisplay(piece.row, piece.col, localSide);
    if (displayRow >= 0 && displayRow < 8 && col >= 0 && col < 8) {
      grid[displayRow][col] = piece;
    }
  }

  return grid;
}
