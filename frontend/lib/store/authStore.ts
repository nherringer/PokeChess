"use client";

import { create } from "zustand";

interface AuthState {
  accessToken: string | null;
  userId: string | null;
  hydrated: boolean;
  setAuth: (token: string, userId: string) => void;
  clearAuth: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  userId: null,
  hydrated: false,

  setAuth: (token: string, userId: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("pokechess_token", token);
      localStorage.setItem("pokechess_user_id", userId);
    }
    set({ accessToken: token, userId });
  },

  clearAuth: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("pokechess_token");
      localStorage.removeItem("pokechess_user_id");
    }
    set({ accessToken: null, userId: null });
  },

  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("pokechess_token");
    const userId = localStorage.getItem("pokechess_user_id");
    if (token && userId) {
      set({ accessToken: token, userId, hydrated: true });
    } else {
      set({ hydrated: true });
    }
  },
}));
