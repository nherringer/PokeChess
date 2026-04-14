import { apiFetch } from "./client";

export interface BotOut {
  id: string;
  name: string;
  label: string;
  flavor: string;
  time_budget: number;
}

export async function getBots(): Promise<BotOut[]> {
  return apiFetch<BotOut[]>("/bots");
}
