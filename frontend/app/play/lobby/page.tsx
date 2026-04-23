import { Suspense } from "react";
import LobbyClient from "./LobbyClient";

export default function LobbyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-bg-deep flex items-center justify-center">
          <span className="text-white/50">Loading...</span>
        </div>
      }
    >
      <LobbyClient />
    </Suspense>
  );
}
