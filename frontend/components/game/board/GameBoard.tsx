"use client";

import React from "react";
import type { BoardPieceData, ForesightEffect, FloorItemData } from "@/lib/types/api";
import type { HighlightType } from "@/lib/game/highlightUtils";
import { apiToDisplay, isTallGrassDisplayRow } from "@/lib/game/boardUtils";
import { BoardSquare } from "./BoardSquare";

interface GameBoardProps {
  grid: (BoardPieceData | null)[][];
  highlightMap: Map<string, HighlightType>;
  pendingForesight: Record<string, ForesightEffect | null>;
  onSquareClick: (row: number, col: number) => void;
  disabled: boolean;
  localSide: "red" | "blue";
  tallGrassExplored: Set<string>;
  floorItemGrid: (FloorItemData | null)[][];
}

export function GameBoard({
  grid,
  highlightMap,
  pendingForesight,
  onSquareClick,
  disabled,
  localSide,
  tallGrassExplored,
  floorItemGrid,
}: GameBoardProps) {
  // Build foresight cell set from display coordinates
  const foresightCells = new Set<string>();
  Object.values(pendingForesight).forEach((effect) => {
    if (effect) {
      const { row: displayRow, col } = apiToDisplay(
        effect.target_row,
        effect.target_col,
        localSide
      );
      foresightCells.add(`${displayRow},${col}`);
    }
  });

  return (
    <div
      className="w-full aspect-square grid grid-cols-8"
      style={{ touchAction: "none" }}
    >
      {grid.map((rowArr, rowIdx) =>
        rowArr.map((piece, colIdx) => {
          const key = `${rowIdx},${colIdx}`;
          const highlight = highlightMap.get(key) ?? null;
          const hasForesight = foresightCells.has(key);
          const isTallGrass = isTallGrassDisplayRow(rowIdx, localSide);
          const isUnexploredGrass = isTallGrass && !tallGrassExplored.has(key);
          const floorItem = floorItemGrid[rowIdx][colIdx];

          return (
            <BoardSquare
              key={key}
              row={rowIdx}
              col={colIdx}
              piece={piece}
              highlight={highlight}
              isSelected={highlight === "select"}
              hasForesight={hasForesight}
              isUnexploredGrass={isUnexploredGrass}
              floorItem={floorItem}
              onClick={() => {
                if (!disabled) {
                  onSquareClick(rowIdx, colIdx);
                }
              }}
            />
          );
        })
      )}
    </div>
  );
}
