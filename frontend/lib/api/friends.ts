import { apiFetch } from "./client";
import type {
  FriendsResponse,
  FriendActionResponse,
} from "@/lib/types/api";

export async function getFriends(): Promise<FriendsResponse> {
  return apiFetch<FriendsResponse>("/friends");
}

export async function sendFriendRequest(identifier: {
  username?: string;
  email?: string;
}): Promise<FriendActionResponse> {
  return apiFetch<FriendActionResponse>("/friends/request", {
    method: "POST",
    body: JSON.stringify(identifier),
  });
}

export async function respondToFriend(
  friendshipId: string,
  action: "accept" | "reject"
): Promise<FriendActionResponse> {
  return apiFetch<FriendActionResponse>(`/friends/${friendshipId}/${action}`, {
    method: "POST",
  });
}
