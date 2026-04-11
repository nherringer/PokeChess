"use client";

import React from "react";

interface PokeballWiggleProps {
  onComplete: () => void;
}

export function PokeballWiggle({ onComplete }: PokeballWiggleProps) {
  return (
    <div
      className="absolute inset-0 flex items-center justify-center z-30 pointer-events-none"
    >
      <span
        className="animate-pokeball-wiggle"
        style={{ fontSize: 40, lineHeight: 1 }}
        onAnimationEnd={onComplete}
      >
        ⚪
      </span>
    </div>
  );
}
