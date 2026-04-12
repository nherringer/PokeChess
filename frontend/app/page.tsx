"use client";

import Link from "next/link";

const PARTICLES = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  size: 6 + (i % 3) * 4,
  top: `${10 + (i * 17) % 80}%`,
  left: `${5 + (i * 23) % 90}%`,
  duration: `${3 + (i % 4)}s`,
  delay: `${(i * 0.4) % 2}s`,
  opacity: 0.15 + (i % 3) * 0.07,
}));

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-bg-deep flex flex-col items-center justify-center overflow-hidden px-6">
      {/* CSS-only particle background */}
      {PARTICLES.map((p) => (
        <div
          key={p.id}
          className="absolute rounded-full bg-blue-team pointer-events-none animate-float"
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

      {/* Main content */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-sm w-full gap-6">
        {/* Logo */}
        <div>
          <h1 className="font-display text-5xl font-bold text-white tracking-wide">
            ♟ POKECHESS
          </h1>
          <p className="text-white/50 text-sm mt-1 font-body">
            Where Pokémon meets chess
          </p>
        </div>

        {/* Main action buttons */}
        <div className="flex flex-col gap-3 w-full mt-2">
          <Link
            href="/play"
            className="w-full py-4 rounded-full font-display font-bold text-lg text-white text-center transition-all active:scale-95"
            style={{ backgroundColor: "#E03737" }}
          >
            ▶ Play vs Bot
          </Link>
          <Link
            href="/friends?invite=true"
            className="w-full py-4 rounded-full font-display font-bold text-lg text-white text-center transition-all active:scale-95"
            style={{ backgroundColor: "#3C72E0" }}
          >
            Play vs Friend
          </Link>
        </div>

        {/* Login CTA — players must authenticate first */}
        <Link
          href="/login"
          className="w-full py-3 rounded-full font-display font-bold text-base text-center border-2 border-white/30 text-white hover:border-white/60 hover:bg-white/5 transition-all active:scale-95"
        >
          Log In / Register
        </Link>

        {/* Nav links */}
        <div className="flex gap-6">
          {[
            { label: "My Pokémon", href: "/roster" },
            { label: "Friends", href: "/friends" },
            { label: "Games", href: "/games" },
          ].map(({ label, href }) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-white/50 hover:text-white transition-colors"
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
