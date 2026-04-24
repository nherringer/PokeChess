"use client";

import { create } from "zustand";
import type { GameDetail, LegalMoveOut } from "@/lib/types/api";

interface GameStoreState {
  game: GameDetail | null;
  localPlayerSide: "red" | "blue" | null;
  selectedSquare: { row: number; col: number } | null;
  legalMoves: LegalMoveOut[];
  quickAttackStep: 0 | 1;
  quickAttackTarget: { row: number; col: number } | null;
  pendingPokeballCell: { row: number; col: number } | null;
  disambigMoves: LegalMoveOut[] | null;

  // actions
  setGame: (game: GameDetail, localSide: "red" | "blue") => void;
  selectSquare: (row: number, col: number) => void;
  setLegalMoves: (moves: LegalMoveOut[]) => void;
  startQuickAttack: (targetRow: number, targetCol: number) => void;
  clearSelection: () => void;
  setPendingPokeball: (cell: { row: number; col: number } | null) => void;
  setDisambigMoves: (moves: LegalMoveOut[] | null) => void;
  reset: () => void;
}

const initialState = {
  game: null,
  localPlayerSide: null,
  selectedSquare: null,
  legalMoves: [],
  quickAttackStep: 0 as const,
  quickAttackTarget: null,
  pendingPokeballCell: null,
  disambigMoves: null,
};

export const useGameStore = create<GameStoreState>((set) => ({
  ...initialState,

  setGame: (game: GameDetail, localSide: "red" | "blue") => {
    set({ game, localPlayerSide: localSide });
  },

  selectSquare: (row: number, col: number) => {
    set({
      selectedSquare: { row, col },
      // Picking a new piece abandons any in-progress Quick Attack flow.
      quickAttackStep: 0,
      quickAttackTarget: null,
    });
  },

  setLegalMoves: (moves: LegalMoveOut[]) => {
    set({ legalMoves: moves });
  },

  startQuickAttack: (targetRow: number, targetCol: number) => {
    set({
      quickAttackStep: 1,
      quickAttackTarget: { row: targetRow, col: targetCol },
    });
  },

  clearSelection: () => {
    set({
      selectedSquare: null,
      legalMoves: [],
      quickAttackStep: 0,
      quickAttackTarget: null,
      disambigMoves: null,
    });
  },

  setPendingPokeball: (cell: { row: number; col: number } | null) => {
    set({ pendingPokeballCell: cell });
  },

  setDisambigMoves: (moves: LegalMoveOut[] | null) => {
    set({ disambigMoves: moves });
  },

  reset: () => {
    set(initialState);
  },
}));
