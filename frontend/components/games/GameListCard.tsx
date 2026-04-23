"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import type { GameSummary } from "@/lib/types/api";
import {
  activeTurnLabel,
  completedResultLabel,
  opponentHeadline,
} from "@/lib/game/gameListLabels";

function StatusBadge({ status }: { status: GameSummary["status"] }) {
  const colors: Record<GameSummary["status"], string> = {
    active: "bg-green-500/20 text-green-400",
    pending: "bg-yellow-500/20 text-yellow-400",
    complete: "bg-white/10 text-white/50",
  };
  return (
    <span className={["text-xs px-2 py-0.5 rounded-full font-bold", colors[status]].join(" ")}>
      {status}
    </span>
  );
}

export function GameListCard({ game }: { game: GameSummary }) {
  const turnLine = activeTurnLabel(game);
  const resultLine = completedResultLabel(game);

  return (
    <div className="bg-bg-card rounded-xl p-4 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <p className="font-display font-bold text-white text-base truncate mb-1">
          {opponentHeadline(game)}
        </p>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <StatusBadge status={game.status} />
          <span className="text-xs text-text-muted">Turn {game.turn_number}</span>
        </div>
        {turnLine && (
          <p className="text-sm text-white/90 font-medium">{turnLine}</p>
        )}
        {resultLine && (
          <p className="text-xs text-accent-gold mt-0.5">{resultLine}</p>
        )}
      </div>
      {game.status === "active" && (
        <Link href={`/game?id=${game.id}`}>
          <Button size="sm" variant="secondary">
            Resume
          </Button>
        </Link>
      )}
      {game.status === "complete" && (
        <Link href={`/game/over?gameId=${game.id}`}>
          <Button size="sm" variant="ghost">
            Review
          </Button>
        </Link>
      )}
    </div>
  );
}
