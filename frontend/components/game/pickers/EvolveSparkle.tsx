import React from "react";

interface EvolveSparkleProps {
  children: React.ReactNode;
  className?: string;
}

export function EvolveSparkle({ children, className = "" }: EvolveSparkleProps) {
  return (
    <div
      className={[
        "animate-sparkle cursor-pointer",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}
