import type { InviteOut } from "@/lib/types/api";

/** Collapse duplicate pending rows for the same pair (keeps newest by created_at). */
export function dedupeInvitesByPlayerPair(invites: InviteOut[]): InviteOut[] {
  const map = new Map<string, InviteOut>();
  for (const inv of invites) {
    const a = String(inv.inviter_id);
    const b = String(inv.invitee_id);
    const key = [a, b].sort().join(":");
    const prev = map.get(key);
    if (
      !prev ||
      new Date(inv.created_at).getTime() > new Date(prev.created_at).getTime()
    ) {
      map.set(key, inv);
    }
  }
  return [...map.values()].sort(
    (x, y) =>
      new Date(y.created_at).getTime() - new Date(x.created_at).getTime()
  );
}
