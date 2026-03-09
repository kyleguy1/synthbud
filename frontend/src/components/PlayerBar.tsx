import { formatDuration } from "../lib/format";
import { usePlayer } from "../state/PlayerContext";

export function PlayerBar() {
  const { state, togglePlayPause, seekTo } = usePlayer();
  const disabled = !state.sound?.previewUrl;

  return (
    <footer className="player-bar">
      <button type="button" onClick={() => void togglePlayPause()} disabled={disabled}>
        {state.isPlaying ? "Pause" : "Play"}
      </button>

      <div className="player-meta">
        <strong>{state.sound?.name || "No sound selected"}</strong>
        <span>{state.sound?.author || ""}</span>
      </div>

      <input
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
    </footer>
  );
}
