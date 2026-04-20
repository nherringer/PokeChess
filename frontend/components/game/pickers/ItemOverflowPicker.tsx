"use client";

import React from "react";
import type { LegalMoveOut } from "@/lib/types/api";
import { DisambiguationSheet } from "./DisambiguationSheet";
import { ITEM_EMOJIS } from "@/lib/constants";

interface ItemOverflowPickerProps {
  open: boolean;
  moves: LegalMoveOut[];
  existingItem: string;
  newItem: string;
  onPick: (move: LegalMoveOut) => void;
  onClose: () => void;
}

function ItemButton({
  label,
  item,
  sublabel,
  onClick,
}: {
  label: string;
  item: string;
  sublabel: string;
  onClick: () => void;
}) {
  const emoji = ITEM_EMOJIS[item] ?? "❓";
  const displayName = item.toLowerCase().replace(/_/g, " ");

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 p-3 rounded-xl bg-bg-card hover:bg-white/10 transition-all flex-1 border border-white/10"
    >
      <span style={{ fontSize: 28 }}>{emoji}</span>
      <span className="text-white font-bold text-sm capitalize">{displayName}</span>
      <span className="text-white/50 text-xs">{label}</span>
      <span className="text-white/40 text-xs">{sublabel}</span>
    </button>
  );
}

export function ItemOverflowPicker({
  open,
  moves,
  existingItem,
  newItem,
  onPick,
  onClose,
}: ItemOverflowPickerProps) {
  const keepExistingMove = moves.find((m) => m.overflow_keep === "existing") ?? null;
  const keepNewMove = moves.find((m) => m.overflow_keep === "new") ?? null;

  return (
    <DisambiguationSheet
      open={open}
      title="Your bag is full — keep which item?"
      onClose={onClose}
    >
      <div className="flex gap-3">
        {keepExistingMove && (
          <ItemButton
            label="Keep"
            item={existingItem}
            sublabel="Drop new item"
            onClick={() => onPick(keepExistingMove)}
          />
        )}
        {keepNewMove && (
          <ItemButton
            label="Keep"
            item={newItem}
            sublabel="Drop old item"
            onClick={() => onPick(keepNewMove)}
          />
        )}
      </div>
    </DisambiguationSheet>
  );
}
