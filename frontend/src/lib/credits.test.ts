import { buildCreditsText } from "./credits";
import type { FavoriteSound } from "../types";

describe("buildCreditsText", () => {
  it("builds expected credit lines", () => {
    const sounds: FavoriteSound[] = [
      {
        id: 9,
        name: "Lead",
        author: "Ava",
        durationSec: 2,
        tags: [],
        licenseLabel: "CC-BY",
        previewUrl: "https://example.com/lead.mp3",
        fileUrl: null,
        sourceUrl: "https://example.com/source"
      }
    ];

    const text = buildCreditsText(sounds);

    expect(text).toContain("Lead - Ava - CC-BY - https://example.com/source");
  });
});
