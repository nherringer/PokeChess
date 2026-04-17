"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { PokeChessLogo } from "@/components/ui/PokeChessLogo";
import { StarfieldBg } from "@/components/ui/StarfieldBg";
import { useAuthStore } from "@/lib/store/authStore";

const PIECE_ROW = [
  { sprite: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/7.png", name: "Squirtle", piece: "Rook", icon: "♜" },
  { sprite: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png", name: "Charmander", piece: "Knight", icon: "♞" },
  { sprite: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png", name: "Bulbasaur", piece: "Bishop", icon: "♝" },
];

export default function HomePage() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrated = useAuthStore((s) => s.hydrated);

  useEffect(() => {
    if (hydrated && accessToken) {
      router.replace("/my-pokemon");
    }
  }, [hydrated, accessToken, router]);

  return (
    <div className="relative min-h-screen bg-bg-deep flex flex-col items-center justify-center overflow-hidden px-6">
      <StarfieldBg showGlow particleCount={5} />

      {/* Pikachu — left character */}
      <div
        className="absolute pointer-events-none select-none hidden sm:block"
        style={{ left: "2%", top: "12%", zIndex: 0 }}
      >
        <Image
          src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
          alt="Pikachu"
          width={180}
          height={180}
          className="opacity-30 scale-x-[-1]"
          style={{ filter: "drop-shadow(0 0 24px rgba(255,203,5,0.3))" }}
          unoptimized
        />
      </div>

      {/* Eevee — right character */}
      <div
        className="absolute pointer-events-none select-none hidden sm:block"
        style={{ right: "2%", top: "12%", zIndex: 0 }}
      >
        <Image
          src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png"
          alt="Eevee"
          width={180}
          height={180}
          className="opacity-30"
          style={{ filter: "drop-shadow(0 0 24px rgba(59,94,229,0.3))" }}
          unoptimized
        />
      </div>

      {/* Dark vignette */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 40%, rgba(13,15,26,0.85) 100%)",
          zIndex: 1,
        }}
      />

      {/* Main content */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-sm w-full gap-6 animate-page-enter">
        {/* Logo */}
        <div className="flex flex-col items-center gap-2">
          <PokeChessLogo size="lg" />
          <p className="text-text-muted text-sm font-body">
            Where Pokémon meets chess
          </p>
        </div>

        {/* CTA buttons */}
        <div className="flex flex-col gap-3 w-full">
          <Link
            href="/register"
            className="w-full py-4 rounded-full font-display font-bold text-lg text-white text-center transition-all hover:scale-[1.03] hover:brightness-110 active:scale-95"
            style={{ backgroundColor: "#E53935" }}
          >
            Register
          </Link>
          <Link
            href="/login"
            className="w-full py-4 rounded-full font-display font-bold text-lg text-white text-center transition-all hover:scale-[1.03] hover:brightness-110 active:scale-95"
            style={{ backgroundColor: "#3B5EE5" }}
          >
            Sign In
          </Link>
        </div>

        {/* Piece showcase row */}
        <div className="flex justify-center gap-8 mt-1">
          {PIECE_ROW.map(({ sprite, name, piece, icon }) => (
            <div key={name} className="flex flex-col items-center gap-1">
              <Image
                src={sprite}
                alt={name}
                width={64}
                height={64}
                className="opacity-90"
                unoptimized
              />
              <span className="text-xl">{icon}</span>
              <span className="text-text-muted text-xs font-body">{piece}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
