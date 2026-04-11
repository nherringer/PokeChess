"use client";

import React, { useState } from "react";

interface BottomDrawerProps {
  peek: React.ReactNode;
  expanded: React.ReactNode;
  className?: string;
}

export function BottomDrawer({ peek, expanded, className = "" }: BottomDrawerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={[
        "relative bg-bg-panel border-t border-white/10 transition-all duration-300 ease-in-out",
        isExpanded ? "h-[300px]" : "h-[60px]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Handle / toggle button */}
      <button
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full flex flex-col items-center justify-center py-2 gap-0.5 hover:bg-white/5 transition-colors"
        aria-label={isExpanded ? "Collapse drawer" : "Expand drawer"}
      >
        <div className="w-10 h-1 rounded-full bg-white/30" />
      </button>

      {/* Peek content — always visible when collapsed */}
      {!isExpanded && (
        <div className="px-4 py-1 text-sm text-white/70 truncate">{peek}</div>
      )}

      {/* Expanded content */}
      {isExpanded && (
        <div className="overflow-y-auto h-[calc(100%-40px)] px-4 pb-4">
          <div className="mb-2 text-sm text-white/50">{peek}</div>
          {expanded}
        </div>
      )}
    </div>
  );
}
