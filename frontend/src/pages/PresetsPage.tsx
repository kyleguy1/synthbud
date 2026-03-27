import { useEffect, useMemo, useState } from "react";
import { ApiError, listPresets, listSynths } from "../api/client";
import type { PresetFilters, PresetSummary } from "../types";

const DEFAULT_FILTERS: PresetFilters = {
  q: "",
  synth: "",
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
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<PresetsPageError | null>(null);

  useEffect(() => {
    void listSynths()
      .then(setSynths)
      .catch(() => setSynths([]));
  }, []);

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

  return (
    <main className="presets-page">
      <section className="presets-controls">
        <input
          type="search"
          placeholder="Search presets, pack, author..."
          value={filters.q}
          onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value, page: 1 }))}
        />
        <select
          value={filters.synth}
          onChange={(event) => setFilters((prev) => ({ ...prev, synth: event.target.value, page: 1 }))}
        >
          <option value="">All synths</option>
          {synths.map((synth) => (
            <option key={synth} value={synth}>
              {synth}
            </option>
          ))}
        </select>
        <select
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
        <label className="toggle">
          <input
            type="checkbox"
            checked={filters.redistributableOnly}
            onChange={(event) => setFilters((prev) => ({ ...prev, redistributableOnly: event.target.checked, page: 1 }))}
          />
          Redistributable only
        </label>
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
        <p className="empty-state">No presets found for current filters.</p>
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
              <span className="badge">{preset.synth_name}</span>
              <span className="badge">{preset.pack.name}</span>
              <span className="badge">{preset.visibility}</span>
              <span className="badge">{preset.parse_status}</span>
              {preset.pack.license_label ? <span className="badge">{preset.pack.license_label}</span> : null}
            </div>
            <div className="tags">
              {preset.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
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
