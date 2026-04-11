import { PIECE_TYPE_EMOJIS, PIECE_TYPE_LABELS } from "@/lib/constants";

export function getPieceDisplay(pieceType: string): {
  emoji: string;
  label: string;
} {
  return {
    emoji: PIECE_TYPE_EMOJIS[pieceType] ?? "?",
    label: PIECE_TYPE_LABELS[pieceType] ?? pieceType,
  };
}
