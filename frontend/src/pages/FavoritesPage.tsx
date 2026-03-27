import { useEffect, useState } from "react";
import { canShowDownloadLink, getFreesoundSourceUrl } from "../api/client";
import { downloadCredits } from "../lib/credits";
import { formatDuration } from "../lib/format";
import { useFavorites } from "../state/FavoritesContext";
import { usePlayer } from "../state/PlayerContext";

export function FavoritesPage() {
  const { favorites, removeFavorite } = useFavorites();
  const { state: playerState, playSound, togglePlayPause } = usePlayer();
  const [copiedSoundId, setCopiedSoundId] = useState<number | null>(null);

  useEffect(() => {
    if (copiedSoundId === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => setCopiedSoundId(null), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copiedSoundId]);

  const handleCopySourceLink = async (sourceLink: string, soundId: number) => {
    try {
      await navigator.clipboard.writeText(sourceLink);
      setCopiedSoundId(soundId);
    } catch {
      window.open(sourceLink, "_blank", "noopener,noreferrer");
    }
  };

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
          const sourceLink = getFreesoundSourceUrl(sound.sourceUrl, sound.author);
          const label = !sound.previewUrl ? "No preview" : isActive ? (playerState.isPlaying ? "Pause" : "Resume") : "Play preview";

          return (
            <li key={sound.id} className="favorite-row">
              <div>
                <strong>{sound.name}</strong>
                <p>{sound.author || "Unknown creator"}</p>
                <p>{sound.licenseLabel || "Unknown license"} • {formatDuration(sound.durationSec)}</p>
              </div>
              <div className="favorite-actions">
                {hasDownload ? (
                  <a
                    className="download-link"
                    href={sound.fileUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download WAV
                  </a>
                ) : sound.fileUrl ? (
                  <span className="download-unavailable" aria-label="Download unavailable">
                    Download unavailable
                  </span>
                ) : null}
                {sourceLink ? (
                  <button
                    type="button"
                    className="source-link"
                    onClick={() => {
                      void handleCopySourceLink(sourceLink, sound.id);
                    }}
                  >
                    {copiedSoundId === sound.id ? "Link copied" : "Copy Freesound link"}
                  </button>
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
                <button type="button" onClick={() => removeFavorite(sound.id)}>
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
