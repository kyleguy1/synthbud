import type {
  LibraryImportResponse,
  LibraryState,
  PaginatedResponse,
  PresetDetail,
  PresetFilters,
  PresetSummary,
  SearchFilters,
  SoundDetail,
  SoundSummary,
  SoundWaveform,
  TagFacet
} from "../types";
import { getApiBaseUrl } from "../lib/runtime";
import { toSearchParams } from "../lib/query";

export const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const endpoint = `${getApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(endpoint, init);
  } catch {
    throw new ApiError(
      "network",
      "We couldn't load data right now. Please try again in a moment.",
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

export async function listTagFacets(): Promise<TagFacet[]> {
  return request<TagFacet[]>("/api/meta/tag-facets");
}

export async function listPresetTagFacets(source?: string): Promise<TagFacet[]> {
  const params = new URLSearchParams();
  if (source) {
    params.set("source", source);
  }
  const suffix = params.toString();
  return request<TagFacet[]>(`/api/meta/preset-tag-facets${suffix ? `?${suffix}` : ""}`);
}

export async function getSoundDetail(soundId: number): Promise<SoundDetail> {
  return request<SoundDetail>(`/api/sounds/${soundId}`);
}

export async function getSoundWaveform(soundId: number, bins = 72): Promise<SoundWaveform> {
  const normalizedBins = Number.isFinite(bins) ? Math.min(240, Math.max(16, Math.round(bins))) : 72;
  return request<SoundWaveform>(`/api/sounds/${soundId}/waveform?bins=${normalizedBins}`);
}

export async function listPresets(filters: PresetFilters): Promise<PaginatedResponse<PresetSummary>> {
  const params = new URLSearchParams();
  if (filters.q.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.genre) {
    params.set("genre", filters.genre);
  }
  if (filters.type) {
    params.set("type", filters.type);
  }
  if (filters.pack) {
    params.append("pack", filters.pack);
  }
  if (filters.synth) {
    params.append("synth", filters.synth);
  }
  if (filters.source) {
    params.set("source", filters.source);
  }
  if (filters.visibility) {
    params.set("visibility", filters.visibility);
  }
  if (filters.redistributableOnly) {
    params.set("redistributable", "true");
  }
  if (filters.sort && filters.sort !== "default") {
    params.set("sort", filters.sort);
  }
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.pageSize));
  return request<PaginatedResponse<PresetSummary>>(`/api/presets/?${params.toString()}`);
}

export async function getPresetDetail(presetId: number): Promise<PresetDetail> {
  return request<PresetDetail>(`/api/presets/${presetId}`);
}

export async function listSynths(source?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (source) {
    params.set("source", source);
  }
  const suffix = params.toString();
  return request<string[]>(`/api/meta/synths${suffix ? `?${suffix}` : ""}`);
}

export async function listPresetPacks(filters: {
  source?: string;
  synth?: string;
}): Promise<string[]> {
  const params = new URLSearchParams();
  if (filters.source) {
    params.set("source", filters.source);
  }
  if (filters.synth) {
    params.set("synth", filters.synth);
  }
  const suffix = params.toString();
  return request<string[]>(`/api/meta/preset-packs${suffix ? `?${suffix}` : ""}`);
}

export async function listPresetGenres(source?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (source) {
    params.set("source", source);
  }
  const suffix = params.toString();
  return request<string[]>(`/api/meta/preset-genres${suffix ? `?${suffix}` : ""}`);
}

export async function listPresetTypes(source?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (source) {
    params.set("source", source);
  }
  const suffix = params.toString();
  return request<string[]>(`/api/meta/preset-types${suffix ? `?${suffix}` : ""}`);
}

export async function syncPresetIndex(source = "presetshare-index", maxPages = 10): Promise<{
  source: string;
  requested_pages: number;
  scanned_pages: number;
  ingested_count: number;
}> {
  const params = new URLSearchParams();
  params.set("source", source);
  params.set("max_pages", String(maxPages));
  return request(`/api/presets/sync?${params.toString()}`, { method: "POST" });
}

export async function getLibraryState(): Promise<LibraryState> {
  return request<LibraryState>("/api/libraries/");
}

export async function importSampleLibrary(path: string): Promise<LibraryImportResponse> {
  return request<LibraryImportResponse>("/api/libraries/samples/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ path })
  });
}

export async function importPresetLibrary(path: string): Promise<LibraryImportResponse> {
  return request<LibraryImportResponse>("/api/libraries/presets/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ path })
  });
}

export function getPlayableUrl(
  soundId: number,
  previewUrl: string | null
): string {
  return previewUrl || `${getApiBaseUrl()}/api/sounds/${soundId}/preview`;
}

export function getDownloadUrl(soundId: number): string {
  return `${getApiBaseUrl()}/api/sounds/${soundId}/download`;
}

export function isUnavailableDownloadUrl(fileUrl: string | null | undefined): boolean {
  return Boolean(fileUrl && fileUrl.includes("freesound.org/apiv2/sounds/") && fileUrl.includes("/download/"));
}

const FREESOUND_OWNER_URL_RE = /^https?:\/\/freesound\.org\/people\/([^/]+)\/sounds\/(\d+)\/?$/i;
const FREESOUND_API_URL_RE = /^https?:\/\/freesound\.org\/apiv2\/sounds\/(\d+)\/?$/i;
const FREESOUND_API_PATH_RE = /^\/apiv2\/sounds\/(\d+)\/?$/i;

function isInternalDownloadUrl(fileUrl: string | null | undefined): boolean {
  return Boolean(fileUrl && fileUrl.includes("/api/sounds/") && fileUrl.includes("/download"));
}

function isFreesoundSourceUrl(sourceUrl: string | null | undefined): boolean {
  return Boolean(sourceUrl && sourceUrl.includes("freesound.org/people/"));
}

export function normalizeFreesoundSourceUrl(
  sourceUrl: string | null | undefined,
  author?: string | null
): string | null {
  if (!sourceUrl) {
    return null;
  }

  const trimmed = sourceUrl.trim();

  const ownerMatch = trimmed.match(FREESOUND_OWNER_URL_RE);
  if (ownerMatch) {
    const owner = ownerMatch[1];
    const soundId = ownerMatch[2];
    return `https://freesound.org/people/${owner}/sounds/${soundId}/`;
  }

  const apiMatch = trimmed.match(FREESOUND_API_URL_RE) || trimmed.match(FREESOUND_API_PATH_RE);
  if (apiMatch) {
    const soundId = apiMatch[1];
    if (author) {
      return `https://freesound.org/people/${author}/sounds/${soundId}/`;
    }
    return `https://freesound.org/sounds/${soundId}/`;
  }

  return null;
}

export function getFreesoundSourceUrl(
  sourceUrl: string | null | undefined,
  author?: string | null
): string | null {
  return normalizeFreesoundSourceUrl(sourceUrl, author);
}

export function canShowDownloadLink(
  fileUrl: string | null | undefined,
  canDownload: boolean | null | undefined,
  sourceUrl?: string | null
): boolean {
  if (!fileUrl || !canDownload) {
    return false;
  }

  if (isUnavailableDownloadUrl(fileUrl)) {
    return false;
  }

  if (isInternalDownloadUrl(fileUrl) && isFreesoundSourceUrl(sourceUrl)) {
    return false;
  }

  return true;
}
