import type { FavoriteSound } from "../types";
import { loadFavorites, saveFavorites, toggleFavorite } from "./favorites";

const sample: FavoriteSound = {
  id: 1,
  name: "Pluck",
  author: "me",
  durationSec: 1.1,
  tags: ["synth"],
  licenseLabel: "CC0",
  previewUrl: "https://example.com/preview.mp3",
  fileUrl: null,
  canDownload: false,
  sourceUrl: "https://example.com"
};

describe("favorites storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("persists favorites to localStorage", () => {
    saveFavorites([sample]);
    expect(loadFavorites()).toEqual([sample]);
  });

  it("toggles favorites in and out", () => {
    const added = toggleFavorite([], sample);
    expect(added).toHaveLength(1);

    const removed = toggleFavorite(added, sample);
    expect(removed).toEqual([]);
  });

  it("repairs stale freesound download URLs for preview playback", () => {
    saveFavorites([
      {
        ...sample,
        previewUrl: "https://freesound.org/apiv2/sounds/123/download/"
      }
    ]);

    expect(loadFavorites()[0].previewUrl).toBe("http://localhost:8000/api/sounds/1/preview");
  });
});
