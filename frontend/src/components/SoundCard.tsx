import { formatDuration } from "../lib/format";
import type { SoundSummary } from "../types";

interface SoundCardProps {
  sound: SoundSummary;
  isFavorite: boolean;
  onToggleFavorite: (sound: SoundSummary) => void;
  onPreview: (sound: SoundSummary) => void;
}

export function SoundCard({ sound, isFavorite, onToggleFavorite, onPreview }: SoundCardProps) {
  return (
    <article className="sound-card">
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

      <button type="button" onClick={() => onPreview(sound)}>
        Preview
      </button>
    </article>
  );
}
