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
  file_url: "https://example.com/download.wav",
  source_page_url: "https://freesound.org/people/Kai/sounds/1/",
  can_preview: true,
  can_download: true,
  brightness: 3200,
  bpm: 120,
  key: "C"
};

describe("SoundCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

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
    expect(screen.getByText("Duration")).toBeInTheDocument();
    expect(screen.getByText("0:02")).toBeInTheDocument();
    expect(screen.getByText("Brightness")).toBeInTheDocument();
    expect(screen.getByText("3200 Hz")).toBeInTheDocument();
    expect(screen.getByText("BPM")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download WAV" })).toHaveAttribute("href", "http://localhost:8000/api/sounds/1/download");
    expect(screen.getByRole("link", { name: "View on Freesound" })).toHaveAttribute("href", "https://freesound.org/people/Kai/sounds/1/");

    await user.click(screen.getByRole("button", { name: "Play preview" }));
    expect(onPreviewToggle).toHaveBeenCalledWith(sound);
  });

  it("only shows learn more when tags overflow and toggles expansion", async () => {
    const user = userEvent.setup();
    const onPreviewToggle = vi.fn();
    const onFavorite = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "offsetTop", {
      configurable: true,
      get() {
        const text = this.textContent ?? "";
        if (text.includes("synth") || text.includes("pluck")) {
          return 0;
        }
        if (text.includes("lead") || text.includes("retro")) {
          return 24;
        }
        if (text.includes("analog") || text.includes("atmospheric")) {
          return 48;
        }
        return 0;
      }
    });

    const overflowingSound: SoundSummary = {
      ...sound,
      tags: ["synth", "pluck", "lead", "retro", "analog", "atmospheric"]
    };

    render(
      <SoundCard
        sound={overflowingSound}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    const toggle = await screen.findByRole("button", { name: "Learn more" });
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });

  it("hides learn more when tags fit within two rows", () => {
    const onPreviewToggle = vi.fn();
    const onFavorite = vi.fn();

    Object.defineProperty(HTMLElement.prototype, "offsetTop", {
      configurable: true,
      get() {
        const text = this.textContent ?? "";
        if (text.includes("synth") || text.includes("pluck")) {
          return 0;
        }
        if (text.includes("lead") || text.includes("retro")) {
          return 24;
        }
        return 0;
      }
    });

    render(
      <SoundCard
        sound={{ ...sound, tags: ["synth", "pluck", "lead", "retro"] }}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    expect(screen.queryByRole("button", { name: "Learn more" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show less" })).not.toBeInTheDocument();
  });

  it("shows download unavailable for stale Freesound download URLs", () => {
    const onPreviewToggle = vi.fn();
    const onFavorite = vi.fn();

    render(
      <SoundCard
        sound={{
          ...sound,
          file_url: "https://freesound.org/apiv2/sounds/661100/download/",
          can_download: true
        }}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    expect(screen.queryByRole("link", { name: "Download WAV" })).not.toBeInTheDocument();
    expect(screen.queryByText("Download unavailable")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on Freesound" })).toBeInTheDocument();
  });

  it("renders the normalized Freesound source link", () => {
    const onPreviewToggle = vi.fn();
    const onFavorite = vi.fn();

    render(
      <SoundCard
        sound={{
          ...sound,
          source_page_url: "https://freesound.org/apiv2/sounds/661100/",
          author: "Kai"
        }}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    expect(screen.getByRole("link", { name: "View on Freesound" })).toHaveAttribute(
      "href",
      "https://freesound.org/people/Kai/sounds/661100/"
    );
  });
});
