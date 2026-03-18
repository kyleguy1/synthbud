import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SoundCard } from "./SoundCard";
import type { SoundSummary } from "../types";

const sound: SoundSummary = {
  id: 1,
  name: "Bright Pluck",
  author: "Kai",
  duration_sec: 1.8,
  tags: ["synth", "pluck"],
  license_label: "CC0",
  preview_url: "https://example.com/preview.mp3",
  brightness: 3200,
  bpm: 120,
  key: "C"
};

describe("SoundCard", () => {
  it("renders core metadata and actions", async () => {
    const user = userEvent.setup();
    const onPreviewToggle = vi.fn();
    const onFavorite = vi.fn();

    render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    expect(screen.getByText("Bright Pluck")).toBeInTheDocument();
    expect(screen.getByText("Kai")).toBeInTheDocument();
    expect(screen.getByText("CC0")).toBeInTheDocument();
    expect(screen.getByText("0:02")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Play preview" }));
    expect(onPreviewToggle).toHaveBeenCalledWith(sound);
  });
});
