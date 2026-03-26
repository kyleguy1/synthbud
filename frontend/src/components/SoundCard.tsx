import { formatDuration } from "../lib/format";
import type { SoundSummary } from "../types";

interface SoundCardProps {
  sound: SoundSummary;
  isFavorite: boolean;
  isActive: boolean;
  isPlaying: boolean;
  onToggleFavorite: (sound: SoundSummary) => void;
  onPreviewToggle: (sound: SoundSummary) => void;
}

export function SoundCard({
  sound,
  isFavorite,
  isActive,
  isPlaying,
  onToggleFavorite,
  onPreviewToggle
}: SoundCardProps) {
  const hasPreview = Boolean(sound.preview_url);
  const previewLabel = !hasPreview ? "No preview" : isActive ? (isPlaying ? "Pause" : "Resume") : "Play preview";

  return (
    <article className={isActive ? "sound-card active" : "sound-card"}>
      <div className="sound-card-header">
        <div>
          <h3>{sound.name}</h3>
          <p>{sound.author || "Unknown creator"}</p>
        </div>
        <button
          type="button"
          aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
          className={isFavorite ? "heart active" : "heart"}
          onClick={() => onToggleFavorite(sound)}
        >
          {isFavorite ? "♥" : "♡"}
        </button>
      </div>

      <div className="badges">
        <span className="badge">{sound.license_label || "Unknown"}</span>
        <span className="badge">{formatDuration(sound.duration_sec)}</span>
      </div>

      <div className="tags">
        {sound.tags.map((tag) => (
          <span className="tag" key={tag}>{tag}</span>
        ))}
      </div>

      <button
        type="button"
        className={isPlaying && isActive ? "preview-button playing" : "preview-button"}
        onClick={() => onPreviewToggle(sound)}
        disabled={!hasPreview}
      >
        {previewLabel}
      </button>
    </article>
  );
}
