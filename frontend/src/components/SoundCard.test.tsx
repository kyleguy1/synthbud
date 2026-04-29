import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SoundCard } from "./SoundCard";
import { resetSoundWaveformCacheForTests } from "../hooks/useSoundWaveform";
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
    vi.unstubAllGlobals();
    resetSoundWaveformCacheForTests();
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
        currentTime={0}
        playbackDuration={0}
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
        currentTime={0}
        playbackDuration={0}
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
        currentTime={0}
        playbackDuration={0}
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
        currentTime={0}
        playbackDuration={0}
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
        currentTime={0}
        playbackDuration={0}
        onToggleFavorite={onFavorite}
        onPreviewToggle={onPreviewToggle}
      />
    );

    expect(screen.getByRole("link", { name: "View on Freesound" })).toHaveAttribute(
      "href",
      "https://freesound.org/people/Kai/sounds/661100/"
    );
  });

  it("loads a waveform only for the active sound card", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            sound_id: 1,
            bins: 72,
            duration_sec: 1.8,
            peaks: Array.from({ length: 72 }, (_, index) => (index % 6) / 5)
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive
        isPlaying
        currentTime={0.9}
        playbackDuration={1.8}
        onToggleFavorite={vi.fn()}
        onPreviewToggle={vi.fn()}
      />
    );

    expect(screen.getByText("Loading waveform")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Audio waveform preview/i })).toBeInTheDocument();
    expect(screen.getByText("0:01 / 0:02")).toBeInTheDocument();
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith("http://localhost:8000/api/sounds/1/waveform?bins=72", undefined);
    });
  });

  it("does not request a waveform for inactive cards", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive={false}
        isPlaying={false}
        currentTime={0}
        playbackDuration={0}
        onToggleFavorite={vi.fn()}
        onPreviewToggle={vi.fn()}
      />
    );

    expect(screen.queryByRole("img", { name: /Audio waveform preview/i })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("reuses cached waveform data when the active sound card remounts", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          sound_id: 1,
          bins: 72,
          duration_sec: 1.8,
          peaks: [0.2, 0.5, 0.9, 0.4]
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchSpy);

    const firstRender = render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive
        isPlaying={false}
        currentTime={0}
        playbackDuration={1.8}
        onToggleFavorite={vi.fn()}
        onPreviewToggle={vi.fn()}
      />
    );

    await screen.findByRole("img", { name: "Audio waveform preview" });
    firstRender.unmount();

    render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive
        isPlaying={false}
        currentTime={0}
        playbackDuration={1.8}
        onToggleFavorite={vi.fn()}
        onPreviewToggle={vi.fn()}
      />
    );

    expect(screen.getByRole("img", { name: "Audio waveform preview" })).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("shows waveform errors inline and retries on demand", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("missing", {
          status: 404,
          statusText: "Not Found"
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            sound_id: 1,
            bins: 72,
            duration_sec: 1.8,
            peaks: [0.1, 0.4, 0.7, 0.3]
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchSpy);

    render(
      <SoundCard
        sound={sound}
        isFavorite={false}
        isActive
        isPlaying={false}
        currentTime={0}
        playbackDuration={1.8}
        onToggleFavorite={vi.fn()}
        onPreviewToggle={vi.fn()}
      />
    );

    expect(await screen.findByText("Waveform data is not ready yet.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("img", { name: "Audio waveform preview" })).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
