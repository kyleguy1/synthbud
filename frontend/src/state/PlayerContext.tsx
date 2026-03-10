import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { FavoriteSound, PlayerState } from "../types";

interface PlayerContextValue {
  state: PlayerState;
  playSound: (sound: FavoriteSound) => Promise<void>;
  togglePlayPause: () => Promise<void>;
  seekTo: (nextTime: number) => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  if (!audioRef.current) {
    audioRef.current = new Audio();
  }

  const [state, setState] = useState<PlayerState>({
    sound: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    error: null
  });

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    const onTimeUpdate = () => {
      setState((prev) => ({ ...prev, currentTime: audio.currentTime }));
    };

    const onLoadedMetadata = () => {
      setState((prev) => ({ ...prev, duration: Number.isFinite(audio.duration) ? audio.duration : 0 }));
    };

    const onPause = () => {
      setState((prev) => ({ ...prev, isPlaying: false }));
    };

    const onPlay = () => {
      setState((prev) => ({ ...prev, isPlaying: true }));
    };

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("play", onPlay);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("play", onPlay);
    };
  }, []);

  const playSound = useCallback(async (sound: FavoriteSound) => {
    const audio = audioRef.current;
    if (!audio || !sound.previewUrl) {
      return;
    }

    if (audio.src !== sound.previewUrl) {
      audio.src = sound.previewUrl;
      setState({ sound, isPlaying: false, currentTime: 0, duration: 0, error: null });
    } else {
      setState((prev) => ({ ...prev, sound, error: null }));
    }

    try {
      await audio.play();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to play audio";
      setState((prev) => ({ ...prev, isPlaying: false, error: message }));
    }
  }, []);

  const togglePlayPause = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio || !state.sound?.previewUrl) {
      return;
    }

    if (audio.paused) {
      try {
        await audio.play();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to play audio";
        setState((prev) => ({ ...prev, isPlaying: false, error: message }));
      }
    } else {
      audio.pause();
    }
  }, [state.sound?.previewUrl]);

  const seekTo = useCallback((nextTime: number) => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.currentTime = Math.max(0, nextTime);
    setState((prev) => ({ ...prev, currentTime: Math.max(0, nextTime) }));
  }, []);

  const value = useMemo<PlayerContextValue>(
    () => ({
      state,
      playSound,
      togglePlayPause,
      seekTo
    }),
    [playSound, seekTo, state, togglePlayPause]
  );

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer() {
  const context = useContext(PlayerContext);
  if (!context) {
    throw new Error("usePlayer must be used inside PlayerProvider");
  }
  return context;
}
