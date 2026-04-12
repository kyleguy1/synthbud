import type { FavoriteSound } from "../types";
import { getRuntimeConfig, saveTextFile } from "./runtime";

export function buildCreditsText(sounds: FavoriteSound[]): string {
  if (sounds.length === 0) {
    return "No favorites saved.";
  }

  return sounds
    .map((sound) => {
      const creator = sound.author || "Unknown creator";
      const license = sound.licenseLabel || "Unknown license";
      const source = sound.sourceUrl || sound.previewUrl || "N/A";
      return `${sound.name} - ${creator} - ${license} - ${source}`;
    })
    .join("\n");
}

export async function downloadCredits(sounds: FavoriteSound[]): Promise<void> {
  const text = buildCreditsText(sounds);
  if (getRuntimeConfig().capabilities.saveTextFile) {
    await saveTextFile("synthbud-credits.txt", text);
    return;
  }

  await saveTextFile("synthbud-credits.txt", text);
}
