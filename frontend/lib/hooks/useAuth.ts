"use client";

import { useAuthStore } from "@/lib/store/authStore";

export function useAuth() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const userId = useAuthStore((s) => s.userId);

  return {
    isLoggedIn: !!accessToken,
    userId,
    accessToken,
  };
}
