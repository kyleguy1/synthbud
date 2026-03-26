import { formatDuration } from "../lib/format";
import { usePlayer } from "../state/PlayerContext";

export function PlayerBar() {
  const { state, togglePlayPause, seekTo, closePlayer } = usePlayer();
  if (!state.sound) {
    return null;
  }

  const disabled = !state.sound?.previewUrl;

  return (
    <footer className="player-bar">
      <button
        type="button"
        className={state.isPlaying ? "player-toggle playing" : "player-toggle"}
        onClick={() => void togglePlayPause()}
        disabled={disabled}
      >
        {state.isPlaying ? "Pause" : "Play"}
      </button>

      <div className="player-meta">
        <strong>{state.sound.name}</strong>
        <span>{state.sound.author || "Unknown creator"}</span>
      </div>

      <input
        className="player-scrubber"
        type="range"
        min={0}
        max={Math.max(state.duration, 0)}
        step={0.1}
        value={Math.min(state.currentTime, state.duration || 0)}
        onChange={(event) => seekTo(Number(event.target.value))}
        disabled={disabled}
      />

      <span>
        {formatDuration(state.currentTime)} / {formatDuration(state.duration || null)}
      </span>
      <button type="button" className="player-close" onClick={closePlayer} aria-label="Close player">
        X
      </button>
      {state.error ? <span className="player-error">{state.error}</span> : null}
    </footer>
  );
}
