import React from "react";
import { PokeBallSpinner } from "@/components/ui/PokeBallSpinner";

export function BotThinkingOverlay() {
  return (
    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-bg-deep/60 pointer-events-none">
      <PokeBallSpinner size={48} />
      <p className="mt-3 font-display font-bold text-white text-base">
        Metallic is thinking...
      </p>
    </div>
  );
}
