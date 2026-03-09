import type { PaginatedResponse, SearchFilters, SoundDetail, SoundSummary } from "../types";
import { toSearchParams } from "../lib/query";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function listSounds(filters: SearchFilters): Promise<PaginatedResponse<SoundSummary>> {
  const query = toSearchParams(filters).toString();
  return request<PaginatedResponse<SoundSummary>>(`/api/sounds/?${query}`);
}

export async function listTags(): Promise<string[]> {
  return request<string[]>("/api/meta/tags");
}

export async function getSoundDetail(soundId: number): Promise<SoundDetail> {
  return request<SoundDetail>(`/api/sounds/${soundId}`);
}
