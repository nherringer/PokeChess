"use client";

import React, { useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { useInvites } from "@/lib/hooks/useInvites";
import { respondToInvite } from "@/lib/api/invites";

function PvBLobby({ gameId }: { gameId: string }) {
  const router = useRouter();

  useEffect(() => {
    const timer = setTimeout(() => {
      router.push(`/game/${gameId}`);
    }, 500);
    return () => clearTimeout(timer);
  }, [router, gameId]);

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center gap-6 px-6">
      <span className="text-6xl animate-bounce-scale">⚡</span>
      <h2 className="font-display text-2xl font-bold text-white">
        Setting up your game...
      </h2>
      {/* Progress bar */}
      <div className="w-48 h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-team rounded-full"
          style={{
            animation: "progress-fill 0.5s ease-out forwards",
            width: "0%",
          }}
        />
      </div>
      <style>{`
        @keyframes progress-fill {
          from { width: 0% }
          to { width: 100% }
        }
      `}</style>
    </div>
  );
}

function PvPLobby({ inviteId }: { inviteId: string }) {
  const router = useRouter();
  const { data: invites } = useInvites();

  // When invite disappears from list (accepted), navigate to game
  useEffect(() => {
    if (!invites) return;
    const invite = invites.find((inv) => inv.id === inviteId);
    // If no longer in list, the friend accepted — navigate to game
    // The game_id would come from the invite that was stored before
    if (invites.length === 0 || !invite) {
      // Try to get game from invite history — for now navigate home
      // In production, we'd track the game_id from createInvite response
      router.push("/games");
    }
  }, [invites, inviteId, router]);

  const handleCancel = async () => {
    try {
      await respondToInvite(inviteId, "reject");
    } catch {
      // ignore
    }
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center gap-6 px-6">
      <div className="flex items-center gap-4 text-4xl">
        <span>👤</span>
        <span className="text-white/30">vs</span>
        <span className="animate-pulse">❓</span>
      </div>
      <h2 className="font-display text-xl font-bold text-white text-center">
        Waiting for your friend to accept...
      </h2>
      <div className="flex items-center gap-3">
        <Spinner size={20} />
        <span className="text-white/50 text-sm">Polling for response...</span>
      </div>
      <Button variant="ghost" size="sm" onClick={handleCancel}>
        Cancel invite
      </Button>
    </div>
  );
}

function LobbyContent() {
  const params = useSearchParams();
  const mode = params.get("mode") ?? "pvb";
  const gameId = params.get("gameId") ?? "";
  const inviteId = params.get("inviteId") ?? "";

  if (mode === "pvp") {
    return <PvPLobby inviteId={inviteId} />;
  }

  return <PvBLobby gameId={gameId} />;
}

export default function LobbyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-bg-deep flex items-center justify-center">
          <span className="text-white/50">Loading...</span>
        </div>
      }
    >
      <LobbyContent />
    </Suspense>
  );
}
