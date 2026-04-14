"use client";

import React from "react";

interface StarfieldBgProps {
  showGlow?: boolean;
  particleCount?: number;
}

function makeParticles(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    size: 4 + (i % 3) * 3,
    top: `${10 + (i * 17) % 80}%`,
    left: `${5 + (i * 23) % 90}%`,
    duration: `${4 + (i % 4)}s`,
    delay: `${(i * 0.5) % 2.5}s`,
    opacity: 0.08 + (i % 3) * 0.04,
  }));
}

export function StarfieldBg({ showGlow = true, particleCount = 5 }: StarfieldBgProps) {
  const particles = makeParticles(particleCount);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      {/* Radial arena glow */}
      {showGlow && (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 60% 40% at 50% 45%, rgba(59,94,229,0.12) 0%, rgba(255,203,5,0.07) 40%, transparent 70%)",
          }}
        />
      )}

      {/* Floating particles */}
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute rounded-full bg-poke-blue animate-float"
          style={{
            width: p.size,
            height: p.size,
            top: p.top,
            left: p.left,
            animationDuration: p.duration,
            animationDelay: p.delay,
            opacity: p.opacity,
          }}
        />
      ))}
    </div>
  );
}
