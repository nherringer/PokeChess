import React from "react";

interface QuickAttackHintProps {
  visible: boolean;
}

export function QuickAttackHint({ visible }: QuickAttackHintProps) {
  if (!visible) return null;

  return (
    <div className="px-4 py-2 bg-yellow-500/10 border-y border-yellow-500/30 text-center">
      <span className="text-yellow-400 text-sm font-bold">
        ⚡ Step 2 of 2 — now pick where to move after attacking
      </span>
    </div>
  );
}
