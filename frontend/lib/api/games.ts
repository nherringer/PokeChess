import { apiFetch } from "./client";
import type {
  GameDetail,
  GamesListResponse,
  CreateGameRequest,
} from "@/lib/types/api";

export async function createGame(req: CreateGameRequest): Promise<GameDetail> {
  return apiFetch<GameDetail>("/games", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getGame(id: string): Promise<GameDetail> {
  return apiFetch<GameDetail>(`/games/${id}`);
}

export async function getGames(): Promise<GamesListResponse> {
  return apiFetch<GamesListResponse>("/games");
}

export async function resignGame(id: string): Promise<GameDetail> {
  return apiFetch<GameDetail>(`/games/${id}/resign`, {
    method: "POST",
  });
}
