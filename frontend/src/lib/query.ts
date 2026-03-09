import type { SearchFilters } from "../types";

export function toSearchParams(filters: SearchFilters): URLSearchParams {
  const params = new URLSearchParams();

  if (filters.q.trim()) {
    params.set("q", filters.q.trim());
  }

  for (const tag of filters.tags) {
    params.append("tags", tag);
  }

  if (filters.cc0Only) {
    params.append("license", "CC0");
  }

  appendNumber(params, "min_duration", filters.minDuration);
  appendNumber(params, "max_duration", filters.maxDuration);
  appendNumber(params, "min_brightness", filters.minBrightness);
  appendNumber(params, "max_brightness", filters.maxBrightness);
  appendNumber(params, "bpm_min", filters.bpmMin);
  appendNumber(params, "bpm_max", filters.bpmMax);

  params.set("page", String(filters.page));
  params.set("page_size", String(filters.pageSize));

  return params;
}

function appendNumber(params: URLSearchParams, key: string, value: number | undefined) {
  if (value !== undefined && Number.isFinite(value)) {
    params.set(key, String(value));
  }
}

export function filtersToUrlParams(filters: SearchFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) {
    params.set("q", filters.q);
  }
  if (filters.cc0Only) {
    params.set("cc0", "1");
  }
  for (const tag of filters.tags) {
    params.append("tag", tag);
  }
  setOptional(params, "minDuration", filters.minDuration);
  setOptional(params, "maxDuration", filters.maxDuration);
  setOptional(params, "minBrightness", filters.minBrightness);
  setOptional(params, "maxBrightness", filters.maxBrightness);
  setOptional(params, "bpmMin", filters.bpmMin);
  setOptional(params, "bpmMax", filters.bpmMax);
  params.set("page", String(filters.page));
  return params;
}

export function filtersFromUrlParams(params: URLSearchParams): SearchFilters {
  return {
    q: params.get("q") ?? "",
    cc0Only: params.get("cc0") === "1",
    tags: params.getAll("tag"),
    minDuration: parseNumber(params.get("minDuration")),
    maxDuration: parseNumber(params.get("maxDuration")),
    minBrightness: parseNumber(params.get("minBrightness")),
    maxBrightness: parseNumber(params.get("maxBrightness")),
    bpmMin: parseNumber(params.get("bpmMin")),
    bpmMax: parseNumber(params.get("bpmMax")),
    page: parseNumber(params.get("page")) ?? 1,
    pageSize: 20
  };
}

function setOptional(params: URLSearchParams, key: string, value: number | undefined) {
  if (value !== undefined) {
    params.set(key, String(value));
  }
}

function parseNumber(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
