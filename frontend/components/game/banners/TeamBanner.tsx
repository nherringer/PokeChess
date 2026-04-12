"use client";

import React from "react";
import type { GameDetail } from "@/lib/types/api";
import { HpBar } from "@/components/ui/HpBar";
import { Button } from "@/components/ui/Button";
import { MAX_HP } from "@/lib/constants";

interface TeamBannerProps {
  team: "red" | "blue";
  game: GameDetail;
  localPlayerSide: "red" | "blue";
  onResign?: () => void;
}

// King piece types per team
const RED_KINGS = ["PIKACHU", "RAICHU"];
const BLUE_KINGS = ["EEVEE", "VAPOREON", "FLAREON", "LEAFEON", "JOLTEON", "ESPEON"];

export function TeamBanner({
  team,
  game,
  localPlayerSide,
  onResign,
}: TeamBannerProps) {
  const isLocalTeam = team === localPlayerSide;
  const teamColor = team === "red" ? "#E03737" : "#3C72E0";
  const teamLabel = team === "red" ? "Team Red" : "Team Blue";
  const teamUpper = team.toUpperCase() as "RED" | "BLUE";

  // Find the king piece for this team
  const kingTypes = team === "red" ? RED_KINGS : BLUE_KINGS;
  const kingPiece = game.state?.board.find(
    (p) => p.team === teamUpper && kingTypes.includes(p.piece_type)
  );

  const kingHp = kingPiece?.current_hp ?? 0;
  const kingMaxHp = kingPiece ? (MAX_HP[kingPiece.piece_type] ?? 200) : 200;

  const isMyTurn = game.whose_turn === team;

  return (
    <div
      className="flex items-center gap-3 px-4 py-2 bg-bg-panel border-b border-white/10"
      style={{ borderLeftColor: teamColor, borderLeftWidth: 3 }}
    >
      {/* Team label */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className="font-display font-bold text-sm"
            style={{ color: teamColor }}
          >
            {teamLabel}
          </span>
          {isMyTurn && (
            <span
              className="text-xs font-bold px-1.5 py-0.5 rounded-full animate-pulse"
              style={{ backgroundColor: `${teamColor}33`, color: teamColor }}
            >
              {isLocalTeam ? "Your Turn!" : "Their Turn"}
            </span>
          )}
          <span className="text-xs text-white/40 ml-auto">
            Turn {game.turn_number}
          </span>
        </div>
        {/* King HP bar */}
        {kingPiece && (
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-white/50 w-12 shrink-0">
              King HP
            </span>
            <HpBar
              current={kingHp}
              max={kingMaxHp}
              className="flex-1"
              color={teamColor}
            />
            <span className="text-xs text-white/50 w-12 text-right shrink-0">
              {kingHp}/{kingMaxHp}
            </span>
          </div>
        )}
      </div>

      {/* Resign button — only for local team */}
      {isLocalTeam && onResign && game.status === "active" && (
        <Button variant="danger" size="sm" onClick={onResign}>
          Resign
        </Button>
      )}
    </div>
  );
}
