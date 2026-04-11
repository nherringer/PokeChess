"use client";

import React from "react";

interface Tab {
  label: string;
  badge?: number;
}

interface TabsProps {
  tabs: Tab[];
  active: number;
  onChange: (index: number) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className = "" }: TabsProps) {
  return (
    <div
      className={["flex border-b border-white/10", className]
        .filter(Boolean)
        .join(" ")}
    >
      {tabs.map((tab, i) => (
        <button
          key={i}
          onClick={() => onChange(i)}
          className={[
            "flex-1 py-2.5 text-sm font-bold transition-all duration-150 relative",
            active === i
              ? "text-blue-team"
              : "text-white/50 hover:text-white/80",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {tab.label}
          {tab.badge !== undefined && tab.badge > 0 && (
            <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-team text-white text-xs font-bold">
              {tab.badge}
            </span>
          )}
          {active === i && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-team rounded-t" />
          )}
        </button>
      ))}
    </div>
  );
}
