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
  page: 1,
  pageSize: 20
};

interface PresetsPageError {
  message: string;
  kind: "network" | "http" | "unknown";
}

const PAGE_SIZE_OPTIONS = [20, 50, 100];

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

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / filters.pageSize)), [total, filters.pageSize]);
  const canGoNext = hasNext ?? filters.page < totalPages;
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

  return (
    <main className="presets-page">
      {showLiveRemoteDiscovery ? (
        <section className="preset-discovery-banner">
          <div>
            <p className="preset-discovery-eyebrow">Online Discovery</p>
            <h2>Search live presets without importing files first</h2>
            <p>
              Browse PresetShare directly in the app, narrow by synth, genre, and sound type,
              then open the preset page when you find something promising.
            </p>
          </div>
        </section>
      ) : null}
      {showIndexedRemoteLibrary ? (
        <section className="preset-discovery-banner">
          <div>
            <p className="preset-discovery-eyebrow">Indexed Online Library</p>
            <h2>Build a larger searchable preset catalog inside the app</h2>
            <p>
              Sync batches of PresetShare metadata into the local database so search and paging
              scale beyond one live scrape.
            </p>
          </div>
          <div className="preset-index-actions">
            <button type="button" onClick={() => void handleSyncIndexedLibrary()} disabled={syncing}>
              {syncing ? "Syncing..." : "Sync 10 pages"}
            </button>
            {syncMessage ? <p>{syncMessage}</p> : null}
            {syncError ? <p className="error">{syncError}</p> : null}
          </div>
        </section>
      ) : null}

      <section className="presets-controls">
        <input
          type="search"
          aria-label="Search presets"
          placeholder={showLiveRemoteDiscovery ? "Search preset names or creators..." : "Search presets, bank, author..."}
          value={filters.q}
          onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value, page: 1 }))}
        />
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
              page: 1
            }))
          }
        >
          <option value="local-filesystem">Local Library</option>
          <option value="presetshare-index">Indexed Online</option>
          <option value="presetshare">Browse Online</option>
        </select>
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
        {showBankFilter ? (
          <select
            aria-label="Bank"
            value={filters.pack}
            onChange={(event) => setFilters((prev) => ({ ...prev, pack: event.target.value, page: 1 }))}
          >
            <option value="">All banks</option>
            {presetPacks.map((packName) => (
              <option key={packName} value={packName}>
                {packName}
              </option>
            ))}
          </select>
        ) : (
          <select
            aria-label="Genre"
            value={filters.genre}
            onChange={(event) => setFilters((prev) => ({ ...prev, genre: event.target.value, page: 1 }))}
          >
            <option value="">All genres</option>
            {presetGenres.map((genre) => (
              <option key={genre} value={genre}>
                {genre}
              </option>
            ))}
          </select>
        )}
        {showGenreAndTypeFilters ? (
          <select
            aria-label="Sound type"
            value={filters.type}
            onChange={(event) => setFilters((prev) => ({ ...prev, type: event.target.value, page: 1 }))}
          >
            <option value="">All sound types</option>
            {presetTypes.map((typeName) => (
              <option key={typeName} value={typeName}>
                {typeName}
              </option>
            ))}
          </select>
        ) : (
          <select
            aria-label="Visibility"
            value={filters.visibility}
            onChange={(event) =>
              setFilters((prev) => ({
                ...prev,
                visibility: event.target.value as PresetFilters["visibility"],
                page: 1
              }))
            }
          >
            <option value="">All visibility</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        )}
        {showLocalFilters ? (
          <label className="toggle presets-toggle">
            <input
              type="checkbox"
              checked={filters.redistributableOnly}
              onChange={(event) =>
                setFilters((prev) => ({ ...prev, redistributableOnly: event.target.checked, page: 1 }))
              }
            />
            Redistributable only
          </label>
        ) : null}
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
      </section>

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
          <article key={preset.id} className="sound-card preset-card">
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
    </main>
  );
}
