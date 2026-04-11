import { apiFetch } from "./client";
import type { TokenResponse } from "@/lib/types/api";

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: email, password });
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
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
