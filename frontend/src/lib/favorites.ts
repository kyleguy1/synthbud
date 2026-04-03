import { canShowDownloadLink, getDownloadUrl, getPlayableUrl, isUnavailableDownloadUrl } from "../api/client";
import type { FavoriteSound, SoundSummary } from "../types";

const STORAGE_KEY = "synthbud-favorites";

export function loadFavorites(): FavoriteSound[] {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as FavoriteSound[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map((sound) => ({
      ...sound,
      previewUrl: isUnavailableDownloadUrl(sound.previewUrl)
        ? getPlayableUrl(sound.id, null)
        : (sound.previewUrl || getPlayableUrl(sound.id, null)),
      fileUrl: canShowDownloadLink(sound.fileUrl, sound.canDownload, sound.sourceUrl) ? getDownloadUrl(sound.id) : null,
      canDownload: canShowDownloadLink(sound.fileUrl, sound.canDownload, sound.sourceUrl),
    }));
  } catch {
    return [];
  }
}

export function saveFavorites(favorites: FavoriteSound[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
}

export function toggleFavorite(favorites: FavoriteSound[], sound: FavoriteSound): FavoriteSound[] {
  const exists = favorites.some((item) => item.id === sound.id);
  if (exists) {
    return favorites.filter((item) => item.id !== sound.id);
  }
  return [sound, ...favorites];
}

export function isFavorite(favorites: FavoriteSound[], soundId: number): boolean {
  return favorites.some((item) => item.id === soundId);
}

export function soundSummaryToFavorite(sound: SoundSummary): FavoriteSound {
  return {
    id: sound.id,
    name: sound.name,
    author: sound.author,
    durationSec: sound.duration_sec,
    tags: sound.tags,
    licenseLabel: sound.license_label,
    previewUrl: getPlayableUrl(sound.id, sound.preview_url),
    fileUrl: canShowDownloadLink(sound.file_url, sound.can_download, sound.source_page_url) ? getDownloadUrl(sound.id) : null,
    canDownload: canShowDownloadLink(sound.file_url, sound.can_download, sound.source_page_url),
    sourceUrl: sound.source_page_url
  };
}
