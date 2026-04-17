import { apiFetch } from "./client";
import type { TokenResponse } from "@/lib/types/api";

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  username: string,
  email: string,
  password: string
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

export async function refreshToken(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
  });
}
