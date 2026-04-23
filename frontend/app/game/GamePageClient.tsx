"use client";

import React, { useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useGame } from "@/lib/hooks/useGame";
import { useGameStore } from "@/lib/store/gameStore";
import { useAuthStore } from "@/lib/store/authStore";
import { useLegalMoves } from "@/lib/hooks/useLegalMoves";
import { useGameMutation } from "@/lib/hooks/useGameMutation";
import { parseBoardGrid } from "@/lib/game/boardUtils";
import { buildHighlightMap } from "@/lib/game/highlightUtils";
import {
  detectDisambiguation,
  classifyPicker,
  type PickerType,
} from "@/lib/game/disambiguate";
import { displayToApi } from "@/lib/game/boardUtils";
import type { LegalMoveOut, MovePayload } from "@/lib/types/api";

import { GameBoard } from "@/components/game/board/GameBoard";
import { TeamBanner } from "@/components/game/banners/TeamBanner";
import { BotThinkingOverlay } from "@/components/game/banners/BotThinkingOverlay";
import { BottomDrawer } from "@/components/ui/BottomDrawer";
import { LastMoveLog } from "@/components/game/LastMoveLog";
import { SelectedPieceCard } from "@/components/game/SelectedPieceCard";
import { MoveLegend } from "@/components/game/MoveLegend";
import { QuickAttackHint } from "@/components/game/QuickAttackHint";
import { MewAttackPicker } from "@/components/game/pickers/MewAttackPicker";
import { PikachuEvolvePicker } from "@/components/game/pickers/PikachuEvolvePicker";
import { EeveeEvolvePicker } from "@/components/game/pickers/EeveeEvolvePicker";
import { PokeballWiggle } from "@/components/game/animations/PokeballWiggle";
import { Spinner } from "@/components/ui/Spinner";

export default function GamePageClient() {
  const searchParams = useSearchParams();
  const gameId = searchParams.get("id") ?? "";
  const router = useRouter();

  // Hooks
  const { game: polledGame, loading, error } = useGame(gameId);
  const userId = useAuthStore((s) => s.userId);
  const store = useGameStore();
  const { fetchMoves, loading: movesLoading } = useLegalMoves(gameId);
  const { submitMove, resign, loading: mutLoading } = useGameMutation(gameId);

  // Sync polled game into store
  useEffect(() => {
    if (!polledGame) return;
    // Determine local side
    let localSide: "red" | "blue" = "red";
    if (polledGame.red_player_id === userId) localSide = "red";
    else if (polledGame.blue_player_id === userId) localSide = "blue";
    else if (polledGame.is_bot_game) {
      // Player is whichever side the bot is NOT
      localSide = polledGame.bot_side === "red" ? "blue" : "red";
    }
    store.setGame(polledGame, localSide);
  }, [polledGame, userId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Navigate to game over when complete — guard against stale store from a previous game
  useEffect(() => {
    if (store.game?.id === gameId && store.game?.status === "complete") {
      router.push(`/game/over?gameId=${gameId}`);
    }
  }, [store.game?.id, store.game?.status, gameId, router]);

  // Reset store on unmount so a stale game state can't bleed into the next game
  useEffect(() => {
    return () => { store.reset(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const game = store.game;
  const localSide = store.localPlayerSide ?? "red";

  const isMyTurn = game?.whose_turn === localSide;
  const isBotTurn =
    game?.is_bot_game === true && game.whose_turn === game.bot_side;

  // Board data
  const grid = game?.state
    ? parseBoardGrid(game.state, localSide)
    : Array.from({ length: 8 }, () => Array(8).fill(null));

  const highlightMap = buildHighlightMap(
    store.legalMoves,
    store.selectedSquare,
    localSide,
    store.quickAttackStep,
    store.quickAttackTarget
  );

  const pendingForesight = game?.state?.pending_foresight ?? {};

  // Disambiguation state
  const disambigMoves = store.disambigMoves;
  const [pickerType, setPickerType] = React.useState<PickerType | null>(null);
  const [pickerOpen, setPickerOpen] = React.useState(false);

  useEffect(() => {
    if (disambigMoves && disambigMoves.length > 0) {
      const type = classifyPicker(disambigMoves);
      setPickerType(type);
      setPickerOpen(true);
    } else {
      setPickerOpen(false);
    }
  }, [disambigMoves]);

  const handlePickerClose = () => {
    setPickerOpen(false);
    store.setDisambigMoves(null);
    store.clearSelection();
  };

  const handlePickerPick = useCallback(
    async (move: LegalMoveOut) => {
      setPickerOpen(false);
      store.setDisambigMoves(null);
      const payload: MovePayload = { ...move };
      await submitMove(payload);
    },
    [submitMove, store]
  );

  // Board click handler
  const handleSquareClick = useCallback(
    async (displayRow: number, displayCol: number) => {
      if (!isMyTurn || !game) return;

      const { row: apiRow, col: apiCol } = displayToApi(
        displayRow,
        displayCol,
        localSide
      );

      const selectedSq = store.selectedSquare;
      const legalMoves = store.legalMoves;

      // No selection yet
      if (!selectedSq) {
        const piece = grid[displayRow][displayCol];
        if (!piece) return;
        const isOwnPiece = piece.team === localSide.toUpperCase();
        if (!isOwnPiece) return;

        store.selectSquare(displayRow, displayCol);
        await fetchMoves(apiRow, apiCol);
        return;
      }

      // Clicked same square — deselect
      if (selectedSq.row === displayRow && selectedSq.col === displayCol) {
        store.clearSelection();
        return;
      }

      // Check if this is a legal move target
      const movesToTarget = legalMoves.filter((m) => {
        const { row: tDisplayRow, col: tDisplayCol } = displayToApi(
          displayRow,
          displayCol,
          localSide
        );
        return m.target_row === tDisplayRow && m.target_col === tDisplayCol;
      });

      if (movesToTarget.length === 0) {
        // Check if clicking own piece — reselect
        const piece = grid[displayRow][displayCol];
        if (piece && piece.team === localSide.toUpperCase()) {
          store.clearSelection();
          store.selectSquare(displayRow, displayCol);
          await fetchMoves(apiRow, apiCol);
          return;
        }
        // Otherwise, deselect
        store.clearSelection();
        return;
      }

      // Quick attack step 1: select attack target then pick where to move
      if (store.quickAttackStep === 0) {
        const quickAttackMoves = movesToTarget.filter(
          (m) => m.action_type === "QUICK_ATTACK"
        );
        if (quickAttackMoves.length > 0) {
          store.startQuickAttack(apiRow, apiCol);
          return;
        }
      } else if (store.quickAttackStep === 1) {
        // Step 2: submit the quick attack move
        const qaTarget = store.quickAttackTarget;
        if (qaTarget) {
          const secondaryMoves = legalMoves.filter(
            (m) =>
              m.action_type === "QUICK_ATTACK" &&
              m.target_row === qaTarget.row &&
              m.target_col === qaTarget.col &&
              m.secondary_row === apiRow &&
              m.secondary_col === apiCol
          );
          if (secondaryMoves.length > 0) {
            await submitMove({ ...secondaryMoves[0] });
            return;
          }
        }
        store.clearSelection();
        return;
      }

      // Disambiguation check
      const disambig = detectDisambiguation(legalMoves, apiRow, apiCol);
      if (disambig) {
        store.setDisambigMoves(disambig);
        return;
      }

      // Single move — submit directly
      const move = movesToTarget[0];
      await submitMove({ ...move });
    },
    [
      isMyTurn,
      game,
      grid,
      localSide,
      store,
      fetchMoves,
      submitMove,
    ]
  );

  // Selected piece
  const selectedPiece = store.selectedSquare
    ? grid[store.selectedSquare.row]?.[store.selectedSquare.col]
    : null;

  const lastMove = game?.move_history.at(-1);

  // Pokeball animation
  const pendingPokeball = store.pendingPokeballCell;
  const pokeballDisplayCell = pendingPokeball
    ? displayToApi(pendingPokeball.row, pendingPokeball.col, localSide)
    : null;

  if (!gameId) {
    return (
      <div className="h-screen flex items-center justify-center bg-bg-deep flex-col gap-4">
        <p className="text-red-400">No game ID provided.</p>
        <button
          onClick={() => router.push("/")}
          className="text-white/50 underline text-sm"
        >
          Go home
        </button>
      </div>
    );
  }

  if (loading && !game) {
    return (
      <div className="h-screen flex items-center justify-center bg-bg-deep">
        <Spinner size={40} />
      </div>
    );
  }

  if (error && !game) {
    return (
      <div className="h-screen flex items-center justify-center bg-bg-deep flex-col gap-4">
        <p className="text-red-400">{error}</p>
        <button
          onClick={() => router.push("/")}
          className="text-white/50 underline text-sm"
        >
          Go home
        </button>
      </div>
    );
  }

  if (!game) return null;

  const opponentSide: "red" | "blue" = localSide === "red" ? "blue" : "red";

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-bg-deep">
      {/* Opponent team banner (top) */}
      <TeamBanner
        team={opponentSide}
        game={game}
        localPlayerSide={localSide}
        onResign={resign}
      />

      {/* Board — square fits in remaining viewport (avoids overflow / huge cells) */}
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex min-h-0 min-w-0 flex-1 items-center justify-center bg-bg-deep px-2 py-1">
          <div
            className="relative mx-auto aspect-square w-full max-w-full shrink-0"
            style={{
              width: "min(100%, calc(100dvh - 11rem), calc(100dvw - 1rem))",
              maxHeight: "min(100%, calc(100dvh - 11rem))",
            }}
          >
            <GameBoard
              grid={grid}
              highlightMap={highlightMap}
              pendingForesight={pendingForesight}
              onSquareClick={handleSquareClick}
              disabled={!isMyTurn || mutLoading || movesLoading}
              localSide={localSide}
            />

            {isBotTurn && (
              <div className="pointer-events-none absolute inset-0">
                <BotThinkingOverlay />
              </div>
            )}

            {pokeballDisplayCell && (
              <div className="absolute inset-0">
                <PokeballWiggle
                  onComplete={() => store.setPendingPokeball(null)}
                />
              </div>
            )}
          </div>
        </div>

        {/* Quick attack hint */}
        <QuickAttackHint visible={store.quickAttackStep === 1} />
      </div>

      {/* Bottom drawer */}
      <BottomDrawer
        peek={<LastMoveLog entry={lastMove} />}
        expanded={
          <div>
            {selectedPiece && (
              <SelectedPieceCard piece={selectedPiece} index={0} className="mb-3" />
            )}
            <MoveLegend />
          </div>
        }
      />

      {/* Local team banner (bottom) */}
      <TeamBanner
        team={localSide}
        game={game}
        localPlayerSide={localSide}
        onResign={resign}
      />

      {/* Disambiguation pickers */}
      {pickerType === "mew_attack" && (
        <MewAttackPicker
          open={pickerOpen}
          moves={disambigMoves ?? []}
          onPick={handlePickerPick}
          onClose={handlePickerClose}
        />
      )}
      {pickerType === "pikachu_evolve" && (
        <PikachuEvolvePicker
          open={pickerOpen}
          move={disambigMoves?.[0] ?? null}
          onConfirm={handlePickerPick}
          onClose={handlePickerClose}
        />
      )}
      {pickerType === "eevee_evolve" && (
        <EeveeEvolvePicker
          open={pickerOpen}
          moves={disambigMoves ?? []}
          onPick={handlePickerPick}
          onClose={handlePickerClose}
        />
      )}
    </div>
  );
}
