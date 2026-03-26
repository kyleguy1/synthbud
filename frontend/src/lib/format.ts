export function formatDuration(durationSec: number | null): string {
  if (durationSec == null || durationSec < 0 || Number.isNaN(durationSec)) {
    return "Unknown";
  }
  const totalSeconds = Math.round(durationSec);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
