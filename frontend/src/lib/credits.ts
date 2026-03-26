import type { FavoriteSound } from "../types";

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

export function downloadCredits(sounds: FavoriteSound[]): void {
  const text = buildCreditsText(sounds);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "synthbud-credits.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
