import type { MoveHistoryEntry } from "@/lib/types/api";
import { PIECE_TYPE_LABELS } from "@/lib/constants";

function pieceName(pieceType?: string | null): string {
  if (!pieceType) return "Unknown";
  return PIECE_TYPE_LABELS[pieceType] ?? pieceType;
}

export function getLastMoveText(entry: MoveHistoryEntry | undefined): string {
  if (!entry) return "";

  const result = entry.result ?? {};
  const attacker = pieceName(result.attacker_type as string | null);
  const target = pieceName(result.target_type as string | null);
  const damage = result.damage as number | null;
  const multiplier = result.type_multiplier as number | null;

  switch (entry.action_type) {
    case "MOVE":
      return `${attacker} moved.`;

    case "ATTACK":
    case "QUICK_ATTACK": {
      if (!damage) return `${attacker} attacked.`;
      let text = `${attacker} attacked ${target} — ${damage} dmg`;
      if (multiplier && multiplier >= 2) text += " — 2× damage!";
      else if (multiplier && multiplier <= 0.5) text += " — not very effective...";
      else text += "!";
      return text;
    }

    case "POKEBALL_ATTACK": {
      const caught = result.caught as boolean | null;
      if (caught) return `Caught ${target}!`;
      return `Pokéball missed!`;
    }

    case "MASTERBALL_ATTACK": {
      const caught = result.caught as boolean | null;
      if (caught) return `Master Ball caught ${target}!`;
      return `Master Ball missed!`;
    }

    case "FORESIGHT": {
      const targetRow = entry.to_row ?? 0;
      return `Mew used Foresight on row ${targetRow}`;
    }

    case "EVOLVE": {
      const evolved_into = pieceName(result.evolved_into as string | null);
      return `${attacker} evolved into ${evolved_into}!`;
    }

    case "TRADE":
      return `${attacker} traded positions.`;

    case "RELEASE":
      return `${attacker} was released.`;

    default:
      return `${attacker} acted.`;
  }
}
