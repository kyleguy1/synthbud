import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  listPresetGenres,
  listPresetPacks,
  listPresets,
  listPresetTypes,
  listSynths,
  syncPresetIndex
} from "../api/client";
import type { PresetFilters, PresetSummary } from "../types";

const DEFAULT_FILTERS: PresetFilters = {
  q: "",
  synth: "",
  genre: "",
  type: "",
  pack: "",
  source: "local-filesystem",
  visibility: "",
  redistributableOnly: false,
  sort: "default",
  page: 1,
  pageSize: 20
};

interface PresetsPageError {
  message: string;
  kind: "network" | "http" | "unknown";
}

const PAGE_SIZE_OPTIONS = [20, 50, 100];
const SORT_OPTIONS: Array<{ value: PresetFilters["sort"]; label: string }> = [
  { value: "default", label: "Default" },
  { value: "newest", label: "Newest" },
  { value: "most-liked", label: "Most liked" },
  { value: "most-downloaded", label: "Most downloaded" },
  { value: "name-asc", label: "A to Z" }
];

interface PresetSuggestion {
  id: string;
  label: string;
  description: string;
  filters: Partial<PresetFilters>;
}

function pickRotatingValue(values: string[], index: number): string {
  if (values.length === 0) {
    return "";
  }
  const normalizedIndex = ((index % values.length) + values.length) % values.length;
  return values[normalizedIndex] ?? "";
}

function buildSuggestionLabel(parts: string[], fallback: string): string {
  const compact = parts.filter(Boolean);
  return compact.length > 0 ? compact.join(" ") : fallback;
}

function buildFeaturedSuggestions(params: {
  source: PresetFilters["source"];
  synths: string[];
  packs: string[];
  genres: string[];
  types: string[];
  seed: number;
}): PresetSuggestion[] {
  const { source, synths, packs, genres, types, seed } = params;

  if (source === "local-filesystem") {
    const synthA = pickRotatingValue(synths, seed);
    const synthB = pickRotatingValue(synths, seed + 1);
    const packA = pickRotatingValue(packs, seed);

    return [
      {
        id: `local-fresh-${seed}`,
        label: synthA ? `${synthA} Fresh Imports` : "Fresh Imports",
        description: "Newest local presets",
        filters: { synth: synthA, pack: "", sort: "newest", visibility: "", redistributableOnly: false }
      },
      {
        id: `local-bank-${seed}`,
        label: packA || "Bank Spotlight",
        description: "Switch to a different bank",
        filters: { synth: "", pack: packA, sort: "name-asc", visibility: "", redistributableOnly: false }
      },
      {
        id: `local-az-${seed}`,
        label: synthB ? `${synthB} A-Z` : "Alphabetical Browse",
        description: "Browse by name",
        filters: { synth: synthB, pack: "", sort: "name-asc", visibility: "", redistributableOnly: false }
      }
    ];
  }

  const trendingSynth = pickRotatingValue(synths, seed);
  const trendingGenre = pickRotatingValue(genres, seed * 2);
  const trendingType = pickRotatingValue(types, seed * 3);
  const downloadedSynth = pickRotatingValue(synths, seed + 1);
  const downloadedGenre = pickRotatingValue(genres, seed * 2 + 1);
  const downloadedType = pickRotatingValue(types, seed * 3 + 1);
  const newestSynth = pickRotatingValue(synths, seed + 2);
  const newestGenre = pickRotatingValue(genres, seed * 2 + 2);
  const newestType = pickRotatingValue(types, seed * 3 + 2);

  return [
    {
      id: `remote-trending-${seed}`,
      label: buildSuggestionLabel([trendingGenre, trendingType], trendingSynth || "Trending Presets"),
      description: [trendingSynth || "Any synth", "most liked"].join(" · "),
      filters: { synth: trendingSynth, genre: trendingGenre, type: trendingType, sort: "most-liked" }
    },
    {
      id: `remote-downloads-${seed}`,
      label: buildSuggestionLabel([downloadedGenre, downloadedType], downloadedSynth || "Popular Downloads"),
      description: [downloadedSynth || "Any synth", "most downloaded"].join(" · "),
      filters: { synth: downloadedSynth, genre: downloadedGenre, type: downloadedType, sort: "most-downloaded" }
    },
    {
      id: `remote-newest-${seed}`,
      label: buildSuggestionLabel([newestGenre, newestType], newestSynth || "Newest Finds"),
      description: [newestSynth || "Any synth", "newest"].join(" · "),
      filters: { synth: newestSynth, genre: newestGenre, type: newestType, sort: "newest" }
    }
  ];
}

function applySuggestionToFilters(current: PresetFilters, suggestion: PresetSuggestion): PresetFilters {
  if (current.source === "local-filesystem") {
    return {
      ...current,
      q: "",
      synth: suggestion.filters.synth ?? "",
      pack: suggestion.filters.pack ?? "",
      genre: "",
      type: "",
      visibility: suggestion.filters.visibility ?? "",
      redistributableOnly: suggestion.filters.redistributableOnly ?? false,
      sort: suggestion.filters.sort ?? "default",
      page: 1
    };
  }

  return {
    ...current,
    q: "",
    synth: suggestion.filters.synth ?? "",
    genre: suggestion.filters.genre ?? "",
    type: suggestion.filters.type ?? "",
    pack: "",
    visibility: "",
    redistributableOnly: false,
    sort: suggestion.filters.sort ?? "default",
    page: 1
  };
}

export function PresetsPage() {
  const [filters, setFilters] = useState<PresetFilters>(DEFAULT_FILTERS);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [synths, setSynths] = useState<string[]>([]);
  const [presetPacks, setPresetPacks] = useState<string[]>([]);
  const [presetGenres, setPresetGenres] = useState<string[]>([]);
  const [presetTypes, setPresetTypes] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [hasNext, setHasNext] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<PresetsPageError | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [suggestionSeed, setSuggestionSeed] = useState(0);
  const [surprisePresetId, setSurprisePresetId] = useState<number | null>(null);

  const showLiveRemoteDiscovery = filters.source === "presetshare";
  const showIndexedRemoteLibrary = filters.source === "presetshare-index";
  const showGenreAndTypeFilters = showLiveRemoteDiscovery || showIndexedRemoteLibrary;
  const showBankFilter = filters.source === "local-filesystem";
  const showLocalFilters = filters.source === "local-filesystem";

  useEffect(() => {
    void listSynths(filters.source)
      .then(setSynths)
      .catch(() => setSynths([]));
  }, [filters.source, refreshKey]);

  useEffect(() => {
    setSuggestionSeed(0);
    setSurprisePresetId(null);
  }, [filters.source]);

  useEffect(() => {
    if (!showBankFilter) {
      setPresetPacks([]);
      return;
    }

    void listPresetPacks({
      source: filters.source,
      synth: filters.synth || undefined
    })
      .then((nextPacks) => {
        setPresetPacks(nextPacks);
        setFilters((prev) => {
          if (!prev.pack || nextPacks.includes(prev.pack)) {
            return prev;
          }
          return { ...prev, pack: "", page: 1 };
        });
      })
      .catch(() => setPresetPacks([]));
  }, [filters.source, filters.synth, showBankFilter, refreshKey]);

  useEffect(() => {
    if (!showGenreAndTypeFilters) {
      setPresetGenres([]);
      setPresetTypes([]);
      return;
    }

    void Promise.all([listPresetGenres(filters.source), listPresetTypes(filters.source)])
      .then(([genres, types]) => {
        setPresetGenres(genres);
        setPresetTypes(types);
      })
      .catch(() => {
        setPresetGenres([]);
        setPresetTypes([]);
      });
  }, [filters.source, showGenreAndTypeFilters]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void listPresets(filters)
      .then((response) => {
        setPresets(response.items);
        setTotal(response.total);
        setHasNext(response.has_next ?? null);
      })
      .catch((fetchError: unknown) => {
        if (fetchError instanceof ApiError) {
          setError({ kind: fetchError.kind, message: fetchError.message });
        } else if (fetchError instanceof Error) {
          setError({ kind: "unknown", message: fetchError.message });
        } else {
          setError({ kind: "unknown", message: "Unable to load presets." });
        }
        setPresets([]);
        setHasNext(null);
      })
      .finally(() => setLoading(false));
  }, [filters, refreshKey]);

  useEffect(() => {
    setSurprisePresetId((current) => {
      if (current === null) {
        return null;
      }
      return presets.some((preset) => preset.id === current) ? current : null;
    });
  }, [presets]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / filters.pageSize)), [total, filters.pageSize]);
  const canGoNext = hasNext ?? filters.page < totalPages;
  const sortOptions = useMemo(
    () =>
      showLocalFilters
        ? SORT_OPTIONS.filter((option) => !["most-liked", "most-downloaded"].includes(option.value))
        : SORT_OPTIONS,
    [showLocalFilters]
  );
  const activeSortLabel = sortOptions.find((option) => option.value === filters.sort)?.label ?? "Default";
  const activeSourceLabel = showLiveRemoteDiscovery
    ? "Browse Online"
    : showIndexedRemoteLibrary
      ? "Indexed Online"
      : "Local Library";
  const heroEyebrow = showLiveRemoteDiscovery
    ? "Online Discovery"
    : showIndexedRemoteLibrary
      ? "Indexed Online Library"
      : "Local Preset Library";
  const heroTitle = showLiveRemoteDiscovery
    ? "Search live presets without importing files first"
    : showIndexedRemoteLibrary
      ? "Build a larger searchable preset catalog inside the app"
      : "Organize your own banks with the same polished browsing flow";
  const heroDescription = showLiveRemoteDiscovery
    ? "Browse PresetShare directly in the app, narrow by synth, genre, and sound type, then open the preset page when you find something promising."
    : showIndexedRemoteLibrary
      ? "Sync batches of PresetShare metadata into the local database so search and paging scale beyond one live scrape."
      : "Search your imported preset banks with cleaner controls, richer source context, and the same card-based browsing feel as the main sound search.";
  const resultsSummary =
    total === 1
      ? "1 preset in view"
      : `${total.toLocaleString()} presets in view`;
  const featuredSuggestions = useMemo(
    () =>
      buildFeaturedSuggestions({
        source: filters.source,
        synths,
        packs: presetPacks,
        genres: presetGenres,
        types: presetTypes,
        seed: suggestionSeed
      }),
    [filters.source, synths, presetPacks, presetGenres, presetTypes, suggestionSeed]
  );
  const surprisePreset = useMemo(
    () => presets.find((preset) => preset.id === surprisePresetId) ?? null,
    [presets, surprisePresetId]
  );
  const emptyMessage = showLiveRemoteDiscovery
    ? "No online presets matched these filters."
    : showIndexedRemoteLibrary
      ? "No indexed online presets yet. Run a sync to build the searchable catalog."
      : "No presets found for current filters.";

  async function handleSyncIndexedLibrary() {
    setSyncing(true);
    setSyncError(null);
    setSyncMessage(null);
    try {
      const result = await syncPresetIndex("presetshare-index", 10);
      setSyncMessage(
        `Indexed ${result.ingested_count} presets from ${result.scanned_pages} PresetShare page${result.scanned_pages === 1 ? "" : "s"}.`
      );
      setRefreshKey((prev) => prev + 1);
    } catch (syncFetchError) {
      if (syncFetchError instanceof ApiError) {
        setSyncError(syncFetchError.message);
      } else if (syncFetchError instanceof Error) {
        setSyncError(syncFetchError.message);
      } else {
        setSyncError("Unable to sync online presets right now.");
      }
    } finally {
      setSyncing(false);
    }
  }

  function handleSuggestionClick(suggestion: PresetSuggestion) {
    setFilters((prev) => applySuggestionToFilters(prev, suggestion));
    setSurprisePresetId(null);
  }

  function handleRefreshSuggestions() {
    const nextSeed = suggestionSeed + 1;
    const nextSuggestions = buildFeaturedSuggestions({
      source: filters.source,
      synths,
      packs: presetPacks,
      genres: presetGenres,
      types: presetTypes,
      seed: nextSeed
    });
    setSuggestionSeed(nextSeed);
    if (nextSuggestions[0]) {
      setFilters((prev) => applySuggestionToFilters(prev, nextSuggestions[0]));
      setSurprisePresetId(null);
    }
  }

  function handleRandomPreset() {
    if (presets.length === 0) {
      return;
    }
    const currentIndex = presets.findIndex((preset) => preset.id === surprisePresetId);
    let nextIndex = Math.floor(Math.random() * presets.length);
    if (presets.length > 1 && nextIndex === currentIndex) {
      nextIndex = (nextIndex + 1) % presets.length;
    }
    setSurprisePresetId(presets[nextIndex]?.id ?? null);
  }

  return (
    <main className="presets-page">
      <section
        className={
          showLiveRemoteDiscovery
            ? "preset-discovery-banner preset-discovery-banner-online"
            : showIndexedRemoteLibrary
              ? "preset-discovery-banner preset-discovery-banner-indexed"
              : "preset-discovery-banner preset-discovery-banner-local"
        }
      >
        <div className="preset-discovery-copy">
          <p className="preset-discovery-eyebrow">{heroEyebrow}</p>
          <h2>{heroTitle}</h2>
          <p>{heroDescription}</p>
        </div>

        <div className="preset-discovery-side">
          <div className="preset-discovery-stats">
            <div className="preset-stat-card">
              <span>Source</span>
              <strong>{activeSourceLabel}</strong>
            </div>
            <div className="preset-stat-card">
              <span>Results</span>
              <strong>{resultsSummary}</strong>
            </div>
            <div className="preset-stat-card">
              <span>Page size</span>
              <strong>{filters.pageSize} per page</strong>
            </div>
          </div>

          {showIndexedRemoteLibrary ? (
            <div className="preset-index-actions">
              <button
                type="button"
                className="preset-sync-button"
                onClick={() => void handleSyncIndexedLibrary()}
                disabled={syncing}
              >
                {syncing ? "Syncing..." : "Sync 10 pages"}
              </button>
              {syncMessage ? <p className="preset-sync-message">{syncMessage}</p> : null}
              {syncError ? <p className="error preset-sync-message">{syncError}</p> : null}
            </div>
          ) : (
            <p className="preset-discovery-note">
              {showLiveRemoteDiscovery
                ? "Use the filter rail below to move through live PresetShare results."
                : "Imported banks stay searchable here after each local ingestion run."}
            </p>
          )}
        </div>
      </section>

      <div className="presets-workbench">
        <section className="presets-toolbar">
          <div className="preset-search-shell">
            <label className="preset-control preset-control-search">
              <span className="preset-control-label">Search</span>
              <input
                type="search"
                aria-label="Search presets"
                placeholder={showLiveRemoteDiscovery ? "Search preset names or creators..." : "Search presets, bank, author..."}
                value={filters.q}
                onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value, page: 1 }))}
              />
            </label>
          </div>

          <section className="presets-controls" aria-label="Preset filters">
            <label className="preset-control">
              <span className="preset-control-label">Source</span>
              <div className="preset-select-shell">
                <select
                  aria-label="Source"
                  value={filters.source}
                onChange={(event) =>
                  setFilters((prev) => ({
                    ...prev,
                    source: event.target.value as PresetFilters["source"],
                    synth: "",
                    genre: "",
                    type: "",
                    pack: "",
                    visibility: "",
                    redistributableOnly: false,
                    sort: "default",
                    page: 1
                  }))
                }
                >
                  <option value="local-filesystem">Local Library</option>
                  <option value="presetshare-index">Indexed Online</option>
                  <option value="presetshare">Browse Online</option>
                </select>
              </div>
            </label>

            <label className="preset-control">
              <span className="preset-control-label">Synth</span>
              <div className="preset-select-shell">
                <select
                  aria-label="Synth"
                  value={filters.synth}
                  onChange={(event) =>
                    setFilters((prev) => ({
                      ...prev,
                      synth: event.target.value,
                      pack: "",
                      page: 1
                    }))
                  }
                >
                  <option value="">All synths</option>
                  {synths.map((synth) => (
                    <option key={synth} value={synth}>
                      {synth}
                    </option>
                  ))}
                </select>
              </div>
            </label>

            <label className="preset-control">
              <span className="preset-control-label">{showBankFilter ? "Bank" : "Genre"}</span>
              <div className="preset-select-shell">
                <select
                  aria-label={showBankFilter ? "Bank" : "Genre"}
                  value={showBankFilter ? filters.pack : filters.genre}
                  onChange={(event) =>
                    setFilters((prev) => (
                      showBankFilter
                        ? { ...prev, pack: event.target.value, page: 1 }
                        : { ...prev, genre: event.target.value, page: 1 }
                    ))
                  }
                >
                  {showBankFilter ? (
                    <>
                      <option value="">All banks</option>
                      {presetPacks.map((packName) => (
                        <option key={packName} value={packName}>
                          {packName}
                        </option>
                      ))}
                    </>
                  ) : (
                    <>
                      <option value="">All genres</option>
                      {presetGenres.map((genre) => (
                        <option key={genre} value={genre}>
                          {genre}
                        </option>
                      ))}
                    </>
                  )}
                </select>
              </div>
            </label>

            <label className="preset-control">
              <span className="preset-control-label">{showGenreAndTypeFilters ? "Sound type" : "Visibility"}</span>
              <div className="preset-select-shell">
                <select
                  aria-label={showGenreAndTypeFilters ? "Sound type" : "Visibility"}
                  value={showGenreAndTypeFilters ? filters.type : filters.visibility}
                  onChange={(event) =>
                    setFilters((prev) => (
                      showGenreAndTypeFilters
                        ? { ...prev, type: event.target.value, page: 1 }
                        : {
                            ...prev,
                            visibility: event.target.value as PresetFilters["visibility"],
                            page: 1
                          }
                    ))
                  }
                >
                  {showGenreAndTypeFilters ? (
                    <>
                      <option value="">All sound types</option>
                      {presetTypes.map((typeName) => (
                        <option key={typeName} value={typeName}>
                          {typeName}
                        </option>
                      ))}
                    </>
                  ) : (
                    <>
                      <option value="">All visibility</option>
                      <option value="public">Public</option>
                      <option value="private">Private</option>
                    </>
                  )}
                </select>
              </div>
            </label>

            <label className="preset-control">
              <span className="preset-control-label">Sort</span>
              <div className="preset-select-shell">
                <select
                  aria-label="Sort"
                  value={filters.sort}
                  onChange={(event) =>
                    setFilters((prev) => ({
                      ...prev,
                      sort: event.target.value as PresetFilters["sort"],
                      page: 1
                    }))
                  }
                >
                  {sortOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </label>

            <label className="preset-control">
              <span className="preset-control-label">Page size</span>
              <div className="preset-select-shell">
                <select
                  aria-label="Page size"
                  value={String(filters.pageSize)}
                  onChange={(event) =>
                    setFilters((prev) => ({
                      ...prev,
                      pageSize: Number(event.target.value),
                      page: 1
                    }))
                  }
                >
                  {PAGE_SIZE_OPTIONS.map((pageSizeOption) => (
                    <option key={pageSizeOption} value={pageSizeOption}>
                      {pageSizeOption} per page
                    </option>
                  ))}
                </select>
              </div>
            </label>

            {showLocalFilters ? (
              <label className="preset-control preset-toggle-card">
                <span className="preset-control-label">Library</span>
                <span className="preset-toggle-copy">Redistributable only</span>
                <span className={filters.redistributableOnly ? "preset-toggle-indicator preset-toggle-indicator-active" : "preset-toggle-indicator"} />
                <input
                  aria-label="Redistributable only"
                  type="checkbox"
                  checked={filters.redistributableOnly}
                  onChange={(event) =>
                    setFilters((prev) => ({ ...prev, redistributableOnly: event.target.checked, page: 1 }))
                  }
                />
              </label>
            ) : null}
          </section>

          <section className="preset-suggestion-panel">
            <div className="preset-panel-heading">
              <div>
                <p className="preset-discovery-eyebrow">Try Something New</p>
                <h3>Discovery shortcuts</h3>
              </div>
              <div className="preset-panel-actions">
                <button
                  type="button"
                  className="preset-secondary-button"
                  onClick={handleRefreshSuggestions}
                >
                  Refresh suggestions
                </button>
                <button
                  type="button"
                  className="preset-secondary-button"
                  onClick={handleRandomPreset}
                  disabled={presets.length === 0}
                >
                  Random preset
                </button>
              </div>
            </div>

            <div className="preset-suggestion-list">
              {featuredSuggestions.map((suggestion) => (
                <button
                  key={suggestion.id}
                  type="button"
                  className="preset-suggestion-chip"
                  onClick={() => handleSuggestionClick(suggestion)}
                >
                  <strong>{suggestion.label}</strong>
                  <span>{suggestion.description}</span>
                </button>
              ))}
            </div>

            {surprisePreset ? (
              <article className="preset-surprise-card">
                <p className="preset-discovery-eyebrow">Surprise Pick</p>
                <strong>{surprisePreset.name}</strong>
                <p>
                  {[surprisePreset.author ?? "Unknown author", surprisePreset.synth_name].filter(Boolean).join(" · ")}
                </p>
                <div className="badges">
                  <span className="badge">{surprisePreset.pack.name}</span>
                  {surprisePreset.like_count ? <span className="badge">{surprisePreset.like_count} likes</span> : null}
                  {surprisePreset.download_count ? <span className="badge">{surprisePreset.download_count} downloads</span> : null}
                </div>
                {(surprisePreset.source_url || surprisePreset.author_url) ? (
                  <div className="preset-card-links">
                    {surprisePreset.source_url ? (
                      <a href={surprisePreset.source_url} target="_blank" rel="noreferrer">
                        Open preset page
                      </a>
                    ) : null}
                    {surprisePreset.author_url ? (
                      <a href={surprisePreset.author_url} target="_blank" rel="noreferrer">
                        View creator
                      </a>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ) : (
              <p className="preset-discovery-note">
                Refresh suggestions to rotate synths and styles, or pick a random preset from the current results.
              </p>
            )}
          </section>
        </section>

        <section className="presets-results-shell">
          <div className="presets-results-header">
            <div>
              <p className="preset-discovery-eyebrow">Results</p>
              <h3>{activeSourceLabel}</h3>
            </div>
            <div className="presets-results-meta">
              <span>{resultsSummary}</span>
              <span>{activeSortLabel}</span>
              <span>{showLiveRemoteDiscovery ? `Page ${filters.page}` : `Page ${filters.page} of ${totalPages}`}</span>
            </div>
          </div>

          {loading ? <p>Loading presets...</p> : null}
          {error ? (
            <p className="error">
              {error.kind === "network"
                ? "We couldn't load presets right now. Please try again in a moment."
                : error.message}
            </p>
          ) : null}

          {!loading && !error && presets.length === 0 ? (
            <p className="empty-state">{emptyMessage}</p>
          ) : null}

          <section className="sound-grid">
            {presets.map((preset) => (
              <article
                key={preset.id}
                className={surprisePreset?.id === preset.id ? "sound-card preset-card preset-card-spotlight" : "sound-card preset-card"}
              >
                <div className="sound-card-header">
                  <div>
                    <h3>{preset.name}</h3>
                    <p>{preset.author ?? "Unknown author"}</p>
                  </div>
                </div>
                <div className="badges">
                  <span className="badge">{preset.source_key ?? preset.pack.source_key ?? "internal"}</span>
                  <span className="badge">{preset.synth_name}</span>
                  <span className="badge">{preset.pack.name}</span>
                  <span className="badge">{preset.visibility}</span>
                  <span className="badge">{preset.parse_status}</span>
                  {preset.pack.license_label ? <span className="badge">{preset.pack.license_label}</span> : null}
                </div>
                {(preset.posted_label || preset.like_count || preset.download_count || preset.comment_count) ? (
                  <div className="preset-remote-meta">
                    {preset.posted_label ? <span>Posted {preset.posted_label}</span> : null}
                    {typeof preset.like_count === "number" ? <span>{preset.like_count} likes</span> : null}
                    {typeof preset.download_count === "number" ? <span>{preset.download_count} downloads</span> : null}
                    {typeof preset.comment_count === "number" ? <span>{preset.comment_count} comments</span> : null}
                  </div>
                ) : null}
                <div className="tags">
                  {preset.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
                {(preset.source_url || preset.author_url) ? (
                  <div className="preset-card-links">
                    {preset.source_url ? (
                      <a href={preset.source_url} target="_blank" rel="noreferrer">
                        Open preset page
                      </a>
                    ) : null}
                    {preset.author_url ? (
                      <a href={preset.author_url} target="_blank" rel="noreferrer">
                        View creator
                      </a>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ))}
          </section>

          <div className="pagination">
            <button
              type="button"
              disabled={filters.page <= 1}
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page - 1 }))}
            >
              Prev
            </button>
            <span>
              {showLiveRemoteDiscovery ? `Page ${filters.page}` : `Page ${filters.page} / ${totalPages}`}
            </span>
            <button
              type="button"
              disabled={!canGoNext}
              onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
            >
              Next
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
