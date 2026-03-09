import type { PaginatedResponse, SearchFilters, SoundDetail, SoundSummary } from "../types";
import { toSearchParams } from "../lib/query";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type ApiErrorKind = "network" | "http";

export class ApiError extends Error {
  kind: ApiErrorKind;
  endpoint: string;
  status?: number;

  constructor(kind: ApiErrorKind, message: string, endpoint: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.endpoint = endpoint;
    this.status = status;
  }
}

async function request<T>(path: string): Promise<T> {
  const endpoint = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(endpoint);
  } catch {
    throw new ApiError(
      "network",
      `Backend unreachable at ${API_BASE_URL}. Check ${API_BASE_URL}/api/health/.`,
      endpoint
    );
  }

  if (!response.ok) {
    throw new ApiError(
      "http",
      `Request failed (${response.status}) for ${path}`,
      endpoint,
      response.status
    );
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
