import { apiFetch } from "./client";
import type { InviteOut, InviteActionResponse } from "@/lib/types/api";

export async function getInvites(): Promise<InviteOut[]> {
  return apiFetch<InviteOut[]>("/game-invites");
}

export async function createInvite(
  inviteeId: string,
  playerSide: "red" | "blue" | "random"
): Promise<InviteActionResponse> {
  return apiFetch<InviteActionResponse>("/game-invites", {
    method: "POST",
    body: JSON.stringify({ invitee_id: inviteeId, player_side: playerSide }),
  });
}

export async function respondToInvite(
  inviteId: string,
  action: "accept" | "reject"
): Promise<InviteActionResponse> {
  return apiFetch<InviteActionResponse>(`/game-invites/${inviteId}`, {
    method: "PUT",
    body: JSON.stringify({ action }),
  });
}

/** Inviter cancels a pending invite (invitees use respondToInvite with reject). */
export async function cancelInviteAsInviter(inviteId: string): Promise<InviteActionResponse> {
  return apiFetch<InviteActionResponse>(`/game-invites/${inviteId}`, {
    method: "DELETE",
  });
}
