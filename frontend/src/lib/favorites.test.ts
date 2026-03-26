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
});
