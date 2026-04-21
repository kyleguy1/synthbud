import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, getSoundWaveform } from "../api/client";
import type { SoundWaveform } from "../types";

interface UseSoundWaveformOptions {
  soundId: number | null;
  bins?: number;
  enabled?: boolean;
}

interface UseSoundWaveformResult {
  data: SoundWaveform | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const DEFAULT_BINS = 72;
const waveformCache = new Map<string, SoundWaveform>();
const inflightWaveforms = new Map<string, Promise<SoundWaveform>>();

function normalizeBins(bins = DEFAULT_BINS): number {
  return Number.isFinite(bins) ? Math.min(240, Math.max(16, Math.round(bins))) : DEFAULT_BINS;
}

function getWaveformKey(soundId: number, bins: number): string {
  return `${soundId}:${bins}`;
}

function getWaveformErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === "network") {
      return "Waveform is offline right now. Try again in a moment.";
    }
    return "Waveform data is not ready yet.";
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Waveform is unavailable right now.";
}

function loadWaveform(soundId: number, bins: number): Promise<SoundWaveform> {
  const cacheKey = getWaveformKey(soundId, bins);
  const cached = waveformCache.get(cacheKey);
  if (cached) {
    return Promise.resolve(cached);
  }

  const inflight = inflightWaveforms.get(cacheKey);
  if (inflight) {
    return inflight;
  }

  const request = getSoundWaveform(soundId, bins)
    .then((waveform) => {
      waveformCache.set(cacheKey, waveform);
      inflightWaveforms.delete(cacheKey);
      return waveform;
    })
    .catch((error: unknown) => {
      inflightWaveforms.delete(cacheKey);
      throw error;
    });

  inflightWaveforms.set(cacheKey, request);
  return request;
}

export function useSoundWaveform({
  soundId,
  bins = 72,
  enabled = true
}: UseSoundWaveformOptions): UseSoundWaveformResult {
  const normalizedBins = useMemo(() => normalizeBins(bins), [bins]);
  const cacheKey = soundId != null ? getWaveformKey(soundId, normalizedBins) : null;
  const [data, setData] = useState<SoundWaveform | null>(() => {
    if (!cacheKey) {
      return null;
    }
    return waveformCache.get(cacheKey) ?? null;
  });
  const [loading, setLoading] = useState(enabled && cacheKey != null && !waveformCache.has(cacheKey));
  const [error, setError] = useState<string | null>(null);
  const [requestNonce, setRequestNonce] = useState(0);

  useEffect(() => {
    if (!enabled || soundId == null || !cacheKey) {
      setLoading(false);
      setError(null);
      setData(cacheKey ? (waveformCache.get(cacheKey) ?? null) : null);
      return;
    }

    const cached = waveformCache.get(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setData(null);
    setLoading(true);
    setError(null);

    void loadWaveform(soundId, normalizedBins)
      .then((waveform) => {
        if (cancelled) {
          return;
        }
        setData(waveform);
        setLoading(false);
      })
      .catch((fetchError: unknown) => {
        if (cancelled) {
          return;
        }
        setData(null);
        setError(getWaveformErrorMessage(fetchError));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [cacheKey, enabled, normalizedBins, requestNonce, soundId]);

  const reload = useCallback(() => {
    if (!cacheKey) {
      return;
    }
    waveformCache.delete(cacheKey);
    inflightWaveforms.delete(cacheKey);
    setRequestNonce((current) => current + 1);
  }, [cacheKey]);

  return { data, loading, error, reload };
}

export function resetSoundWaveformCacheForTests(): void {
  waveformCache.clear();
  inflightWaveforms.clear();
}
