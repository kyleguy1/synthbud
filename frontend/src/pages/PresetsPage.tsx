import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  listPresetGenres,
  listPresetPacks,
  listPresets,
  listPresetTypes,
  listSynths
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

export function PresetsPage() {
  const [filters, setFilters] = useState<PresetFilters>(DEFAULT_FILTERS);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [synths, setSynths] = useState<string[]>([]);
  const [presetPacks, setPresetPacks] = useState<string[]>([]);
  const [presetGenres, setPresetGenres] = useState<string[]>([]);
  const [presetTypes, setPresetTypes] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<PresetsPageError | null>(null);

  const showRemoteDiscovery = filters.source === "presetshare";
  const showBankFilter = !showRemoteDiscovery;
  const showLocalFilters = !showRemoteDiscovery;

  useEffect(() => {
    void listSynths(filters.source)
      .then(setSynths)
      .catch(() => setSynths([]));
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
  }, [filters.source, filters.synth, showBankFilter]);

  useEffect(() => {
    if (!showRemoteDiscovery) {
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
  }, [filters.source, showRemoteDiscovery]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void listPresets(filters)
      .then((response) => {
        setPresets(response.items);
        setTotal(response.total);
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
      })
      .finally(() => setLoading(false));
  }, [filters]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / filters.pageSize)), [total, filters.pageSize]);
  const emptyMessage = showRemoteDiscovery
    ? "No online presets matched these filters."
    : "No presets found for current filters.";

  return (
    <main className="presets-page">
      {showRemoteDiscovery ? (
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

      <section className="presets-controls">
        <input
          type="search"
          aria-label="Search presets"
          placeholder={showRemoteDiscovery ? "Search preset names or creators..." : "Search presets, bank, author..."}
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
        {showRemoteDiscovery ? (
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
          Page {filters.page} / {totalPages}
        </span>
        <button
          type="button"
          disabled={filters.page >= totalPages}
          onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
        >
          Next
        </button>
      </div>
    </main>
  );
}
