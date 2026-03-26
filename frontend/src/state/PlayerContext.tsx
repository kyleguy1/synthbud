import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { FavoriteSound, PlayerState } from "../types";

interface PlayerContextValue {
  state: PlayerState;
  playSound: (sound: FavoriteSound) => Promise<void>;
  togglePlayPause: () => Promise<void>;
  seekTo: (nextTime: number) => void;
  closePlayer: () => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

function isIgnorablePlaybackError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

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
      setState((prev) => ({ ...prev, isPlaying: false, error: null }));
    };

    const onPlay = () => {
      setState((prev) => ({ ...prev, isPlaying: true, error: null }));
    };

    const onEnded = () => {
      setState((prev) => ({
        ...prev,
        isPlaying: false,
        currentTime: Number.isFinite(audio.duration) ? audio.duration : prev.currentTime
      }));
    };

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("ended", onEnded);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("ended", onEnded);
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
      if (isIgnorablePlaybackError(error)) {
        setState((prev) => ({ ...prev, isPlaying: false, error: null }));
        return;
      }
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
        if (isIgnorablePlaybackError(error)) {
          setState((prev) => ({ ...prev, isPlaying: false, error: null }));
          return;
        }
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

  const closePlayer = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) {
      return;
    }

    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    setState({
      sound: null,
      isPlaying: false,
      currentTime: 0,
      duration: 0,
      error: null
    });
  }, []);

  const value = useMemo<PlayerContextValue>(
    () => ({
      state,
      playSound,
      togglePlayPause,
      seekTo,
      closePlayer
    }),
    [closePlayer, playSound, seekTo, state, togglePlayPause]
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
