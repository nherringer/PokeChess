"use client";

import React from "react";
import { Button } from "@/components/ui/Button";

interface DisambiguationSheetProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function DisambiguationSheet({
  open,
  title,
  onClose,
  children,
}: DisambiguationSheetProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-md bg-bg-panel rounded-t-xl p-4 pb-8 animate-slide-up"
        style={{ maxHeight: 300 }}
      >
        <div className="w-10 h-1 bg-white/30 rounded-full mx-auto mb-4" />
        <h3 className="font-display font-bold text-white text-lg mb-4 text-center">
          {title}
        </h3>
        {children}
        <div className="mt-4">
          <Button variant="ghost" size="sm" fullWidth onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
