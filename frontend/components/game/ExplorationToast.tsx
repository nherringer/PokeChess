"use client";

import React, { useEffect, useState } from "react";
import { ITEM_EMOJIS } from "@/lib/constants";

interface ExplorationEvent {
  id: number;
  item: string | null; // null = explored but no item
}

interface ExplorationToastProps {
  events: ExplorationEvent[];
  onDismiss: (id: number) => void;
}

function ToastItem({
  event,
  onDismiss,
}: {
  event: ExplorationEvent;
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(event.id), 3000);
    return () => clearTimeout(t);
  }, [event.id, onDismiss]);

  const hasItem = event.item && event.item !== "NONE";
  const emoji = hasItem ? (ITEM_EMOJIS[event.item!] ?? "❓") : "🌿";
  const text = hasItem ? `Found ${event.item!.toLowerCase().replace("_", " ")}!` : "Explored tall grass";

  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-xl text-white text-sm font-medium shadow-lg pointer-events-auto"
      style={{ backgroundColor: hasItem ? "#2a5c2a" : "#1a3a1a", border: "1px solid #4a9a4a" }}
    >
      <span style={{ fontSize: 16 }}>{emoji}</span>
      <span>{text}</span>
    </div>
  );
}

export function ExplorationToast({ events, onDismiss }: ExplorationToastProps) {
  if (events.length === 0) return null;

  return (
    <div className="absolute top-2 left-1/2 -translate-x-1/2 flex flex-col gap-1 z-50 pointer-events-none">
      {events.map((ev) => (
        <ToastItem key={ev.id} event={ev} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export type { ExplorationEvent };
