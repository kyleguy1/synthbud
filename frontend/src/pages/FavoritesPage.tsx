import { Link } from "react-router-dom";
import { canShowDownloadLink, getFreesoundSourceUrl } from "../api/client";
import { downloadCredits } from "../lib/credits";
import { formatDuration } from "../lib/format";
import { useFavorites } from "../state/FavoritesContext";
import { usePlayer } from "../state/PlayerContext";

function formatCollectionLength(totalSeconds: number): string {
  if (totalSeconds <= 0) {
    return "< 1 min";
  }

  const totalMinutes = Math.max(1, Math.round(totalSeconds / 60));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0 && minutes > 0) {
    return `${hours} hr ${minutes} min`;
  }
  if (hours > 0) {
    return `${hours} hr`;
  }
  return `${totalMinutes} min`;
}

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function FavoritesPage() {
  const { favorites, removeFavorite } = useFavorites();
  const { state: playerState, playSound, togglePlayPause } = usePlayer();
  const previewReadyCount = favorites.filter((sound) => Boolean(sound.previewUrl)).length;
  const downloadReadyCount = favorites.filter((sound) =>
    canShowDownloadLink(sound.fileUrl, sound.canDownload, sound.sourceUrl)
  ).length;
  const uniqueCreators = new Set(favorites.map((sound) => sound.author || "Unknown creator")).size;
  const uniqueLicenses = new Set(favorites.map((sound) => sound.licenseLabel || "Unknown license")).size;
  const totalDurationSeconds = favorites.reduce((sum, sound) => sum + (sound.durationSec ?? 0), 0);
  const resultsSummary = pluralize(favorites.length, "favorite");

  return (
    <main className="favorites-page">
      <section className="favorites-hero">
        <div className="favorites-hero-copy">
          <p className="favorites-eyebrow">Saved Collection</p>
          <h2>Keep your best finds in a polished listening library</h2>
          <p>
            Preview favorite sounds, jump back to their source pages, and export clean credit notes without
            leaving the app.
          </p>
        </div>

        <div className="favorites-hero-side">
          <div className="favorites-hero-stats">
            <div className="favorite-stat-card">
              <span>Saved</span>
              <strong>{resultsSummary}</strong>
            </div>
            <div className="favorite-stat-card">
              <span>Preview ready</span>
              <strong>{pluralize(previewReadyCount, "sound")}</strong>
            </div>
            <div className="favorite-stat-card">
              <span>Download ready</span>
              <strong>{pluralize(downloadReadyCount, "sound")}</strong>
            </div>
          </div>

          <div className="favorites-hero-actions">
            <button
              type="button"
              className="favorite-primary-button"
              onClick={() => downloadCredits(favorites)}
              disabled={favorites.length === 0}
            >
              Export credits
            </button>
            <p className="favorites-note">
              Favorites stay stored in this browser, so you can keep curating a personal library as you explore.
            </p>
          </div>
        </div>
      </section>

      <div className="favorites-workbench">
        <aside className="favorites-sidebar">
          <section className="favorites-panel">
            <div className="favorites-panel-heading">
              <p className="favorites-eyebrow">Collection Snapshot</p>
              <h3>At a glance</h3>
            </div>

            <div className="favorite-summary-list">
              <div className="favorite-summary-item">
                <span>Total listening time</span>
                <strong>{formatCollectionLength(totalDurationSeconds)}</strong>
              </div>
              <div className="favorite-summary-item">
                <span>Creators saved</span>
                <strong>{pluralize(uniqueCreators, "creator")}</strong>
              </div>
              <div className="favorite-summary-item">
                <span>Licenses represented</span>
                <strong>{pluralize(uniqueLicenses, "license")}</strong>
              </div>
            </div>
          </section>

          <section className="favorites-panel">
            <div className="favorites-panel-heading">
              <p className="favorites-eyebrow">Quick Actions</p>
              <h3>Keep exploring</h3>
            </div>

            <div className="favorite-action-stack">
              <Link className="favorite-secondary-link" to="/">
                Browse sound search
              </Link>
              <p className="favorites-note">
                Star sounds from the search page and they will land here with previews, source links, and exportable
                credits.
              </p>
            </div>
          </section>
        </aside>

        <section className="favorites-results-shell">
          <div className="favorites-results-header">
            <div>
              <p className="favorites-eyebrow">Library</p>
              <h3>Saved favorites</h3>
            </div>

            <div className="favorites-results-meta">
              <span>{resultsSummary}</span>
              <span>{pluralize(previewReadyCount, "preview")} ready</span>
              <span>{pluralize(downloadReadyCount, "download")} ready</span>
            </div>
          </div>

          {favorites.length === 0 ? (
            <div className="favorites-empty-state">
              <p className="favorites-eyebrow">Nothing saved yet</p>
              <h3>Start starring sounds from Search</h3>
              <p>
                Once you favorite sounds, they will show up here for quick previewing, clean credit exports, and easy
                revisits to the original source pages.
              </p>
              <div className="favorites-empty-actions">
                <Link className="favorite-primary-link" to="/">
                  Browse sound search
                </Link>
              </div>
            </div>
          ) : (
            <ul className="favorites-list">
              {favorites.map((sound) => {
                const isActive = playerState.sound?.id === sound.id;
                const hasDownload = canShowDownloadLink(sound.fileUrl, sound.canDownload, sound.sourceUrl);
                const sourceLink = getFreesoundSourceUrl(sound.sourceUrl, sound.author) ?? undefined;
                const label = !sound.previewUrl
                  ? "No preview"
                  : isActive
                    ? (playerState.isPlaying ? "Pause" : "Resume")
                    : "Play preview";
                const previewStatus = !sound.previewUrl
                  ? "No preview"
                  : isActive && playerState.isPlaying
                    ? "Now playing"
                    : "Preview ready";

                return (
                  <li key={sound.id} className="favorite-row">
                    <div className="favorite-card-head">
                      <div className="favorite-copy">
                        <strong>{sound.name}</strong>
                        <p>{sound.author || "Unknown creator"}</p>
                        <div className="favorite-meta">
                          <span>{formatDuration(sound.durationSec)}</span>
                          <span>{hasDownload ? "Download ready" : "Stream or source only"}</span>
                        </div>
                      </div>
                      <span
                        className={
                          isActive && playerState.isPlaying
                            ? "favorite-card-status favorite-card-status-active"
                            : "favorite-card-status"
                        }
                      >
                        {previewStatus}
                      </span>
                    </div>

                    <div className="favorite-badges">
                      <span className="badge">{sound.licenseLabel || "Unknown license"}</span>
                      {sound.previewUrl ? <span className="badge">Preview ready</span> : <span className="badge">No preview</span>}
                      {hasDownload ? <span className="badge">Download ready</span> : null}
                    </div>

                    {sound.tags.length > 0 ? (
                      <div className="tags">
                        {sound.tags.slice(0, 5).map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="favorite-actions">
                      {hasDownload ? (
                        <a className="download-link" href={sound.fileUrl ?? undefined} target="_blank" rel="noreferrer">
                          Download WAV
                        </a>
                      ) : null}
                      {sourceLink ? (
                        <a className="source-link" href={sourceLink} target="_blank" rel="noreferrer">
                          View on Freesound
                        </a>
                      ) : null}
                      <button
                        type="button"
                        className={isActive && playerState.isPlaying ? "preview-button playing" : "preview-button"}
                        onClick={() => {
                          if (isActive) {
                            void togglePlayPause();
                            return;
                          }
                          void playSound(sound);
                        }}
                        disabled={!sound.previewUrl}
                      >
                        {label}
                      </button>
                      <button type="button" className="favorite-remove" onClick={() => removeFavorite(sound.id)}>
                        Remove
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
