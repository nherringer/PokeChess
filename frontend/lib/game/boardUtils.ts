import type { GameStateData, BoardPieceData, FloorItemData } from "@/lib/types/api";

export function flipRow(row: number, localSide: "red" | "blue"): number {
  return localSide === "blue" ? 7 - row : row;
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

export function parseFloorItemGrid(
  floorItems: FloorItemData[],
  localSide: "red" | "blue"
): (FloorItemData | null)[][] {
  const grid: (FloorItemData | null)[][] = Array.from({ length: 8 }, () =>
    Array(8).fill(null)
  );
  for (const fi of floorItems) {
    const { row: displayRow, col } = apiToDisplay(fi.row, fi.col, localSide);
    if (displayRow >= 0 && displayRow < 8 && col >= 0 && col < 8) {
      grid[displayRow][col] = fi;
    }
  }
  return grid;
}

export function parseTallGrassExplored(
  explored: [number, number][],
  localSide: "red" | "blue"
): Set<string> {
  const result = new Set<string>();
  for (const [apiRow, apiCol] of explored) {
    const { row: displayRow, col } = apiToDisplay(apiRow, apiCol, localSide);
    result.add(`${displayRow},${col}`);
  }
  return result;
}

export function isTallGrassDisplayRow(
  displayRow: number,
  localSide: "red" | "blue"
): boolean {
  const apiRow = flipRow(displayRow, localSide);
  return apiRow >= 2 && apiRow <= 5;
}
