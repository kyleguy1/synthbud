import { canShowDownloadLink, getFreesoundSourceUrl } from "../api/client";
import { downloadCredits } from "../lib/credits";
import { formatDuration } from "../lib/format";
import { useFavorites } from "../state/FavoritesContext";
import { usePlayer } from "../state/PlayerContext";

export function FavoritesPage() {
  const { favorites, removeFavorite } = useFavorites();
  const { state: playerState, playSound, togglePlayPause } = usePlayer();

  return (
    <main className="favorites-page">
      <div className="favorites-header">
        <h2>Favorites</h2>
        <button type="button" onClick={() => downloadCredits(favorites)}>
          Export credits
        </button>
      </div>

      {favorites.length === 0 ? <p>No favorites saved yet.</p> : null}

      <ul className="favorites-list">
        {favorites.map((sound) => {
          const isActive = playerState.sound?.id === sound.id;
          const hasDownload = canShowDownloadLink(sound.fileUrl, sound.canDownload, sound.sourceUrl);
          const sourceLink = getFreesoundSourceUrl(sound.sourceUrl, sound.author) ?? undefined;
          const label = !sound.previewUrl ? "No preview" : isActive ? (playerState.isPlaying ? "Pause" : "Resume") : "Play preview";

          return (
            <li key={sound.id} className="favorite-row">
              <div className="favorite-copy">
                <strong>{sound.name}</strong>
                <p>{sound.author || "Unknown creator"}</p>
                <p>{formatDuration(sound.durationSec)}</p>
                <div className="favorite-badges">
                  <span className="badge">{sound.licenseLabel || "Unknown license"}</span>
                </div>
              </div>
              <div className="favorite-actions">
                {hasDownload ? (
                  <a
                    className="download-link"
                    href={sound.fileUrl ?? undefined}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download WAV
                  </a>
                ) : null}
                {sourceLink ? (
                  <a
                    className="source-link"
                    href={sourceLink}
                    target="_blank"
                    rel="noreferrer"
                  >
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
                <button
                  type="button"
                  className="favorite-remove"
                  onClick={() => removeFavorite(sound.id)}
                >
                  Remove
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
