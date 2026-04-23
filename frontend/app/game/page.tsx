import { Suspense } from "react";
import { Spinner } from "@/components/ui/Spinner";
import GamePageClient from "./GamePageClient";

export default function GamePage() {
  return (
    <Suspense
      fallback={
        <div className="h-screen flex items-center justify-center bg-bg-deep">
          <Spinner size={40} />
        </div>
      }
    >
      <GamePageClient />
    </Suspense>
  );
}
