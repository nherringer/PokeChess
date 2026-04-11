"use client";

import React from "react";
import { useRouter } from "next/navigation";

interface PageShellProps {
  title: string;
  children: React.ReactNode;
  showBack?: boolean;
  backHref?: string;
  rightSlot?: React.ReactNode;
}

export function PageShell({
  title,
  children,
  showBack = true,
  backHref,
  rightSlot,
}: PageShellProps) {
  const router = useRouter();

  const handleBack = () => {
    if (backHref) {
      router.push(backHref);
    } else {
      router.back();
    }
  };

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col">
      {/* Sticky top bar */}
      <header className="sticky top-0 z-40 bg-bg-panel border-b border-white/10 px-4 py-3 flex items-center gap-3">
        {showBack && (
          <button
            onClick={handleBack}
            className="text-xl text-white/70 hover:text-white transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10"
            aria-label="Go back"
          >
            ←
          </button>
        )}
        <h1 className="flex-1 font-display text-lg font-bold text-white">
          {title}
        </h1>
        {rightSlot && <div>{rightSlot}</div>}
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
