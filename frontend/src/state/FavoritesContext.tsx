import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { FavoriteSound, SoundSummary } from "../types";
import { isFavorite, loadFavorites, saveFavorites, soundSummaryToFavorite, toggleFavorite } from "../lib/favorites";

interface FavoritesContextValue {
  favorites: FavoriteSound[];
  isFavoriteSound: (soundId: number) => boolean;
  toggleFromSummary: (sound: SoundSummary) => void;
  removeFavorite: (soundId: number) => void;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<FavoriteSound[]>(() => loadFavorites());

  const value = useMemo<FavoritesContextValue>(
    () => ({
      favorites,
      isFavoriteSound: (soundId) => isFavorite(favorites, soundId),
      toggleFromSummary: (sound) => {
        const next = toggleFavorite(favorites, soundSummaryToFavorite(sound));
        setFavorites(next);
        saveFavorites(next);
      },
      removeFavorite: (soundId) => {
        const next = favorites.filter((item) => item.id !== soundId);
        setFavorites(next);
        saveFavorites(next);
      }
    }),
    [favorites]
  );

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites() {
  const context = useContext(FavoritesContext);
  if (!context) {
    throw new Error("useFavorites must be used inside FavoritesProvider");
  }
  return context;
}
