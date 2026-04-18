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
  password: string,
  accessCode?: string // TEMP: registration gate — remove param for public launch
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    // TEMP: registration gate — remove access_code from body for public launch
    body: JSON.stringify({ username, email, password, access_code: accessCode }),
  });
}

export async function refreshToken(): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
  });
}
