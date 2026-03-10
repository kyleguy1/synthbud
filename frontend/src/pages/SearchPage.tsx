import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, listSounds, listTags } from "../api/client";
import { FiltersSidebar } from "../components/FiltersSidebar";
import { SoundCard } from "../components/SoundCard";
import { TopBar } from "../components/TopBar";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { soundSummaryToFavorite } from "../lib/favorites";
import { filtersFromUrlParams, filtersToUrlParams } from "../lib/query";
import { useFavorites } from "../state/FavoritesContext";
import { usePlayer } from "../state/PlayerContext";
import type { SearchFilters, SoundSummary } from "../types";

const DEFAULT_FILTERS: SearchFilters = {
  q: "",
  tags: [],
  cc0Only: false,
  page: 1,
  pageSize: 20
};

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFilters = useMemo(() => {
    const loaded = filtersFromUrlParams(searchParams);
    return { ...DEFAULT_FILTERS, ...loaded };
  }, [searchParams]);

  const [filters, setFilters] = useState<SearchFilters>(initialFilters);
  const [sounds, setSounds] = useState<SoundSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<SearchPageError | null>(null);

  const debouncedFilters = useDebouncedValue(filters, 300);
  const { toggleFromSummary, isFavoriteSound } = useFavorites();
  const { playSound } = usePlayer();

  useEffect(() => {
    void listTags()
      .then(setAllTags)
      .catch(() => setAllTags([]));
  }, []);

  useEffect(() => {
    setSearchParams(filtersToUrlParams(filters), { replace: true });
  }, [filters, setSearchParams]);

  useEffect(() => {
    setLoading(true);
    setError(null);

    void listSounds(debouncedFilters)
      .then((response) => {
        setSounds(response.items);
        setTotal(response.total);
      })
      .catch((fetchError: unknown) => {
        if (fetchError instanceof ApiError) {
          setError({ message: fetchError.message, kind: fetchError.kind });
        } else if (fetchError instanceof Error) {
          setError({ message: fetchError.message, kind: "unknown" });
        } else {
          setError({ message: "Unable to fetch sounds", kind: "unknown" });
        }
        setSounds([]);
      })
      .finally(() => setLoading(false));
  }, [debouncedFilters]);

  const totalPages = Math.max(1, Math.ceil(total / filters.pageSize));

  return (
    <main className="search-layout">
      <TopBar
        query={filters.q}
        cc0Only={filters.cc0Only}
        onQueryChange={(q) => setFilters((prev) => ({ ...prev, q, page: 1 }))}
        onToggleCc0={(cc0Only) => setFilters((prev) => ({ ...prev, cc0Only, page: 1 }))}
      />

      <div className="search-content">
        <FiltersSidebar
          tags={allTags}
          selectedTags={filters.tags}
          minDuration={filters.minDuration}
          maxDuration={filters.maxDuration}
          minBrightness={filters.minBrightness}
          maxBrightness={filters.maxBrightness}
          bpmMin={filters.bpmMin}
          bpmMax={filters.bpmMax}
          onToggleTag={(tag) => {
            setFilters((prev) => {
              const hasTag = prev.tags.includes(tag);
              const tags = hasTag ? prev.tags.filter((t) => t !== tag) : [...prev.tags, tag];
              return { ...prev, tags, page: 1 };
            });
          }}
          onRangeChange={(key, value) => {
            setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
          }}
        />

        <section className="sound-grid-section">
          {loading ? <p>Loading sounds...</p> : null}
          {error ? (
            <div className="error-block">
              <p className="error">{error.message}</p>
              {error.kind === "network" ? (
                <p className="error-hint">
                  Backend appears offline. Verify <code>http://localhost:8000/api/health/</code>.
                </p>
              ) : null}
            </div>
          ) : null}
          {!loading && !error && sounds.length === 0 ? (
            <p className="empty-state">
              No sounds found for current filters. Try clearing one or more filters.
            </p>
          ) : null}

          <div className="sound-grid">
            {sounds.map((sound) => (
              <SoundCard
                key={sound.id}
                sound={sound}
                isFavorite={isFavoriteSound(sound.id)}
                onToggleFavorite={toggleFromSummary}
                onPreview={(summary) => {
                  void playSound(soundSummaryToFavorite(summary));
                }}
              />
            ))}
          </div>

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
        </section>
      </div>
    </main>
  );
}
interface SearchPageError {
  message: string;
  kind: "network" | "http" | "unknown";
}
