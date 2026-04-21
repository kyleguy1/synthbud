interface SoundWaveformProps {
  peaks?: number[] | null;
  progress?: number;
  isPlaying?: boolean;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

const WAVEFORM_HEIGHT = 40;
const BAR_WIDTH = 4;
const BAR_GAP = 2;
const LOADING_BAR_COUNT = 24;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function buildLoadingPeaks(): number[] {
  return Array.from({ length: LOADING_BAR_COUNT }, (_, index) => 0.28 + ((index % 6) + 1) * 0.08);
}

export function SoundWaveform({
  peaks,
  progress = 0,
  isPlaying = false,
  loading = false,
  error = null,
  onRetry
}: SoundWaveformProps) {
  const safeProgress = clamp(progress, 0, 1);

  if (error) {
    return (
      <div className="sound-waveform sound-waveform-state sound-waveform-error" role="status">
        <span>{error}</span>
        {onRetry ? (
          <button type="button" className="sound-waveform-retry" onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const bars = peaks && peaks.length > 0 ? peaks : loading ? buildLoadingPeaks() : [];

  if (bars.length === 0) {
    return (
      <div className="sound-waveform sound-waveform-state" role="status">
        <span>Waveform unavailable.</span>
      </div>
    );
  }

  const width = bars.length * (BAR_WIDTH + BAR_GAP) - BAR_GAP;
  const playheadX = width * safeProgress;

  return (
    <div
      className={loading ? "sound-waveform loading" : "sound-waveform"}
      aria-busy={loading}
      data-testid="sound-waveform"
    >
      <svg
        viewBox={`0 0 ${width} ${WAVEFORM_HEIGHT}`}
        role="img"
        aria-label={loading ? "Loading waveform preview" : "Audio waveform preview"}
        preserveAspectRatio="none"
      >
        {bars.map((rawPeak, index) => {
          const peak = clamp(rawPeak, 0.08, 1);
          const barHeight = Math.max(6, peak * (WAVEFORM_HEIGHT - 8));
          const x = index * (BAR_WIDTH + BAR_GAP);
          const y = (WAVEFORM_HEIGHT - barHeight) / 2;
          const isPlayed = !loading && index / bars.length < safeProgress;

          return (
            <rect
              key={`${index}-${peak}`}
              x={x}
              y={y}
              width={BAR_WIDTH}
              height={barHeight}
              rx={BAR_WIDTH / 2}
              className={isPlayed ? "sound-waveform-bar played" : "sound-waveform-bar"}
            />
          );
        })}

        {!loading && (safeProgress > 0 || isPlaying) ? (
          <line
            className={isPlaying ? "sound-waveform-playhead active" : "sound-waveform-playhead"}
            x1={playheadX}
            x2={playheadX}
            y1={4}
            y2={WAVEFORM_HEIGHT - 4}
          />
        ) : null}
      </svg>
    </div>
  );
}
