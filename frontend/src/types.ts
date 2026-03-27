export interface SoundSummary {
  id: number;
  name: string;
  author: string | null;
  duration_sec: number | null;
  tags: string[];
  license_label: string | null;
  preview_url: string | null;
  file_url: string | null;
  source_page_url: string | null;
  can_preview?: boolean;
  can_download?: boolean;
  brightness: number | null;
  bpm: number | null;
  key: string | null;
}

export interface SoundDetail extends SoundSummary {
  source_page_url: string | null;
  file_url: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PresetPackSummary {
  id: number;
  name: string;
  author: string | null;
  synth_name: string;
  synth_vendor: string | null;
  source_url: string | null;
  license_label: string | null;
  is_redistributable: boolean;
  visibility: "public" | "private";
}

export interface PresetSummary {
  id: number;
  name: string;
  author: string | null;
  synth_name: string;
  synth_vendor: string | null;
  tags: string[];
  visibility: "public" | "private";
  is_redistributable: boolean;
  parse_status: "pending" | "success" | "partial" | "failed";
  source_url: string | null;
  pack: PresetPackSummary;
}

export interface PresetDetail extends PresetSummary {
  parse_error: string | null;
  parser_version: string | null;
  imported_at: string;
  updated_at: string;
  raw_payload: Record<string, unknown> | null;
  macro_names: string[];
  macro_values: Record<string, unknown> | null;
  osc_count: number | null;
  fx_enabled: boolean | null;
  filter_enabled: boolean | null;
}

export interface PresetFilters {
  q: string;
  synth: string;
  visibility: "" | "public" | "private";
  redistributableOnly: boolean;
  page: number;
  pageSize: number;
}

export interface SearchFilters {
  q: string;
  tags: string[];
  cc0Only: boolean;
  minDuration?: number;
  maxDuration?: number;
  minBrightness?: number;
  maxBrightness?: number;
  bpmMin?: number;
  bpmMax?: number;
  page: number;
  pageSize: number;
}

export interface FavoriteSound {
  id: number;
  name: string;
  author: string | null;
  durationSec: number | null;
  tags: string[];
  licenseLabel: string | null;
  previewUrl: string | null;
  fileUrl: string | null;
  canDownload?: boolean;
  sourceUrl: string | null;
}

export interface PlayerState {
  sound: FavoriteSound | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  error: string | null;
}
