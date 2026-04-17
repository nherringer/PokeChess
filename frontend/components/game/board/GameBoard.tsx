"use client";

import React from "react";
import type { BoardPieceData, ForesightEffect } from "@/lib/types/api";
import type { HighlightType } from "@/lib/game/highlightUtils";
import { apiToDisplay } from "@/lib/game/boardUtils";
import { BoardSquare } from "./BoardSquare";

interface GameBoardProps {
  grid: (BoardPieceData | null)[][];
  highlightMap: Map<string, HighlightType>;
  pendingForesight: Record<string, ForesightEffect | null>;
  onSquareClick: (row: number, col: number) => void;
  disabled: boolean;
  localSide: "red" | "blue";
}

export function GameBoard({
  grid,
  highlightMap,
  pendingForesight,
  onSquareClick,
  disabled,
  localSide,
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
    <div className="h-full w-full touch-none grid grid-cols-8 grid-rows-8 [grid-template-columns:repeat(8,minmax(0,1fr))] [grid-template-rows:repeat(8,minmax(0,1fr))]">
      {grid.map((rowArr, rowIdx) =>
        rowArr.map((piece, colIdx) => {
          const key = `${rowIdx},${colIdx}`;
          const highlight = highlightMap.get(key) ?? null;
          const hasForesight = foresightCells.has(key);

          return (
            <BoardSquare
              key={key}
              row={rowIdx}
              col={colIdx}
              piece={piece}
              highlight={highlight}
              isSelected={highlight === "select"}
              hasForesight={hasForesight}
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
