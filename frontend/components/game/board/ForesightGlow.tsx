import React from "react";

export function ForesightGlow() {
  return (
    <div
      className="absolute inset-0 pointer-events-none rounded-sm animate-pulse"
      style={{
        background:
          "radial-gradient(circle, rgba(50,215,250,0.35) 0%, rgba(50,215,250,0.0) 80%)",
        boxShadow: "inset 0 0 6px rgba(50,215,250,0.5)",
        border: "2px solid rgba(50,215,250,0.7)",
      }}
    />
  );
}
