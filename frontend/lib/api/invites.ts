import { apiFetch } from "./client";
import type { InviteOut, InviteActionResponse } from "@/lib/types/api";

export async function getInvites(): Promise<InviteOut[]> {
  return apiFetch<InviteOut[]>("/game-invites");
}

export async function createInvite(
  inviteeId: string
): Promise<InviteActionResponse> {
  return apiFetch<InviteActionResponse>("/game-invites", {
    method: "POST",
    body: JSON.stringify({ invitee_id: inviteeId }),
  });
}

export async function respondToInvite(
  inviteId: string,
  action: "accept" | "reject"
): Promise<InviteActionResponse> {
  return apiFetch<InviteActionResponse>(`/game-invites/${inviteId}/${action}`, {
    method: "POST",
  });
}
