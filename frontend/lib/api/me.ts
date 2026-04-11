import { apiFetch } from "./client";
import type { UserProfile } from "@/lib/types/api";

export async function getMe(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/users/me");
}
