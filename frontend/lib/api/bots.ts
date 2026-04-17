import { apiFetch } from "./client";

export interface BotOut {
  id: string;
  name: string;
  stars: number;
  flavor: string;
  forced_player_side: "red" | "blue" | null;
  accent_color: string;
  trainer_sprite: string;
  time_budget: number;
}

export async function getBots(): Promise<BotOut[]> {
  return apiFetch<BotOut[]>("/bots");
}
