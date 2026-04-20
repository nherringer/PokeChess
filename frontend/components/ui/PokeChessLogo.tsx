"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";

interface PokeChessLogoProps {
  size?: "sm" | "lg";
}

const POKE_LETTERS = ["P", "O", "K", "E"];
const CHESS_LETTERS = ["C", "H", "E", "S", "S"];

export function PokeChessLogo({ size = "lg" }: PokeChessLogoProps) {
  const boltRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const el = boltRef.current;
    if (!el) return;
    el.classList.remove("animate-bolt-flash");
    // Trigger reflow to restart animation
    void el.offsetWidth;
    el.classList.add("animate-bolt-flash");
  }, []);

  const isLg = size === "lg";

  return (
    <div
      className="flex items-center justify-center"
      style={{ gap: isLg ? "6px" : "4px" }}
    >
      {/* Pokéball icon */}
      <Image
        src="/pokeball.svg"
        alt=""
        width={isLg ? 36 : 22}
        height={isLg ? 36 : 22}
        className="shrink-0"
        style={{ marginRight: isLg ? 4 : 2 }}
      />

      {/* POKE */}
      <span
        style={{
          fontFamily: "'Fredoka One', sans-serif",
          fontSize: isLg ? "3rem" : "1.75rem",
          lineHeight: 1,
          letterSpacing: "0.05em",
          display: "flex",
          gap: isLg ? "1px" : "0px",
        }}
      >
        {POKE_LETTERS.map((letter) => (
          <span
            key={letter}
            style={{
              color: "#3B5EE5",
              textShadow: "0 0 0 #FFCB05, 1px 1px 0 #FFCB05, -1px -1px 0 #FFCB05, 1px -1px 0 #FFCB05, -1px 1px 0 #FFCB05",
              WebkitTextStroke: isLg ? "1.5px #FFCB05" : "1px #FFCB05",
            }}
          >
            {letter}
          </span>
        ))}
      </span>

      {/* Thunderbolt separator */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={boltRef}
        src="/thunderbolt.svg"
        alt=""
        width={isLg ? 18 : 12}
        height={isLg ? 30 : 20}
        style={{
          filter: "drop-shadow(0 0 8px #FFCB05)",
          margin: isLg ? "0 2px" : "0 1px",
        }}
      />

      {/* CHESS */}
      <span
        style={{
          fontFamily: "'Black Ops One', sans-serif",
          fontSize: isLg ? "3rem" : "1.75rem",
          lineHeight: 1,
          letterSpacing: isLg ? "-0.02em" : "-0.01em",
          display: "flex",
        }}
      >
        {CHESS_LETTERS.map((letter, i) => (
          <span
            key={i}
            style={
              i % 2 === 0
                ? { color: "#F0EAD6" }
                : {
                    color: "#1A1A1A",
                    WebkitTextStroke: "1px #F0EAD6",
                  }
            }
          >
            {letter}
          </span>
        ))}
      </span>

      {/* Pawn icon */}
      <Image
        src="/pawn.svg"
        alt=""
        width={isLg ? 28 : 18}
        height={isLg ? 36 : 22}
        className="shrink-0"
        style={{ marginLeft: isLg ? 4 : 2 }}
      />
    </div>
  );
}
