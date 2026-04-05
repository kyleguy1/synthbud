import { useEffect, useRef, useState } from "react";
import { canShowDownloadLink, getDownloadUrl, getFreesoundSourceUrl } from "../api/client";
import { ExternalLink } from "./ExternalLink";
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
  const hasPreview = sound.can_preview ?? true;
  const hasDownload = canShowDownloadLink(sound.file_url, sound.can_download, sound.source_page_url);
  const sourceLink = getFreesoundSourceUrl(sound.source_page_url, sound.author);
  const showSourceLink = Boolean(sourceLink);
  const previewLabel = !hasPreview ? "No preview" : isActive ? (isPlaying ? "Pause" : "Resume") : "Play preview";
  const soundMeta = [
    { label: "Duration", value: sound.duration_sec != null ? formatDuration(sound.duration_sec) : null },
    { label: "Brightness", value: sound.brightness != null ? `${Math.round(sound.brightness)} Hz` : null },
    { label: "BPM", value: sound.bpm != null ? String(Math.round(sound.bpm)) : null }
  ].filter((item) => item.value);

  useEffect(() => {
    const updateOverflow = () => {
      const tagsElement = tagsRef.current;
      if (!tagsElement) {
        return;
      }

      const rowOffsets = Array.from(tagsElement.children)
        .map((child) => (child as HTMLElement).offsetTop)
        .filter((offset, index, offsets) => offsets.findIndex((value) => Math.abs(value - offset) <= 1) === index);

      setHasOverflow(rowOffsets.length > 2);
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
    setIsExpanded(false);
  }, [sound.id]);

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
        {soundMeta.map((item) => (
          <span key={item.label} className="badge sound-meta-badge">
            <span className="sound-meta-label">{item.label}</span>
            <span className="sound-meta-value">{item.value}</span>
          </span>
        ))}
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

      <div className="sound-card-actions">
        {hasDownload ? (
          <a
            className="download-link"
            href={getDownloadUrl(sound.id)}
            target="_blank"
            rel="noreferrer"
          >
            Download WAV
          </a>
        ) : null}

        {sourceLink ? (
          <ExternalLink
            className="source-link"
            href={sourceLink}
          >
            View on Freesound
          </ExternalLink>
        ) : null}
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
