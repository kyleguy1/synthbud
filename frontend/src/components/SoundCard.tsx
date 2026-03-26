import { useEffect, useRef, useState } from "react";
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
  const tagsRef = useRef<HTMLDivElement | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasOverflow, setHasOverflow] = useState(false);
  const hasPreview = Boolean(sound.preview_url);
  const previewLabel = !hasPreview ? "No preview" : isActive ? (isPlaying ? "Pause" : "Resume") : "Play preview";

  useEffect(() => {
    const updateOverflow = () => {
      const tagsElement = tagsRef.current;
      if (!tagsElement) {
        return;
      }

      setHasOverflow(tagsElement.scrollHeight > tagsElement.clientHeight + 1);
    };

    updateOverflow();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateOverflow);
      return () => window.removeEventListener("resize", updateOverflow);
    }

    const observer = new ResizeObserver(() => updateOverflow());
    if (tagsRef.current) {
      observer.observe(tagsRef.current);
    }

    return () => observer.disconnect();
  }, [sound.tags]);

  useEffect(() => {
    if (!hasOverflow && isExpanded) {
      setIsExpanded(false);
    }
  }, [hasOverflow, isExpanded]);

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

      <div className="sound-card-tags">
        <div
          ref={tagsRef}
          className={isExpanded ? "tags expanded" : "tags collapsed"}
        >
          {sound.tags.map((tag) => (
            <span className="tag" key={tag}>{tag}</span>
          ))}
        </div>

        {hasOverflow ? (
          <button
            type="button"
            className="tag-toggle"
            onClick={() => setIsExpanded((prev) => !prev)}
          >
            {isExpanded ? "Show less" : "Learn more"}
          </button>
        ) : (
          <div className="tag-toggle-spacer" aria-hidden="true" />
        )}
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
