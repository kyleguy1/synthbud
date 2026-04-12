import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const mockDownloadCredits = vi.fn();
const mockCanShowDownloadLink = vi.fn();
const mockGetFreesoundSourceUrl = vi.fn();
const mockUseFavorites = vi.fn();
const mockUsePlayer = vi.fn();
const mockPlaySound = vi.fn();
const mockTogglePlayPause = vi.fn();
const mockRemoveFavorite = vi.fn();

vi.mock("../lib/credits", () => ({
  downloadCredits: (...args: unknown[]) => mockDownloadCredits(...args)
}));

vi.mock("../lib/format", () => ({
  formatDuration: (seconds: number | null) => (seconds ? `${seconds}s` : "0s")
}));

vi.mock("../api/client", () => ({
  canShowDownloadLink: (...args: unknown[]) => mockCanShowDownloadLink(...args),
  getFreesoundSourceUrl: (...args: unknown[]) => mockGetFreesoundSourceUrl(...args)
}));

vi.mock("../state/FavoritesContext", () => ({
  useFavorites: () => mockUseFavorites()
}));

vi.mock("../state/PlayerContext", () => ({
  usePlayer: () => mockUsePlayer()
}));

import { FavoritesPage } from "./FavoritesPage";

const favoriteSound = {
  id: 1,
  name: "Warm Pad",
  author: "Kyle",
  durationSec: 125,
  tags: ["pad", "warm", "analog"],
  licenseLabel: "CC0",
  previewUrl: "https://example.com/preview.mp3",
  fileUrl: "https://example.com/download.wav",
  canDownload: true,
  sourceUrl: "https://freesound.org/people/kyle/sounds/1/"
};

describe("FavoritesPage", () => {
  beforeEach(() => {
    mockCanShowDownloadLink.mockReturnValue(true);
    mockGetFreesoundSourceUrl.mockImplementation((sourceUrl?: string | null) => sourceUrl ?? null);
    mockUseFavorites.mockReturnValue({
      favorites: [favoriteSound],
      removeFavorite: mockRemoveFavorite
    });
    mockUsePlayer.mockReturnValue({
      state: {
        sound: null,
        isPlaying: false,
        currentTime: 0,
        duration: 0,
        error: null
      },
      playSound: mockPlaySound,
      togglePlayPause: mockTogglePlayPause
    });
    mockPlaySound.mockResolvedValue(undefined);
    mockTogglePlayPause.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the upgraded favorites workspace and preserves actions", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <FavoritesPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Keep your best finds in a polished listening library")).toBeInTheDocument();
    expect(screen.getByText("Saved favorites")).toBeInTheDocument();
    expect(screen.getByText("Warm Pad")).toBeInTheDocument();
    expect(screen.getByText("pad")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse sound search" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Download WAV" })).toHaveAttribute(
      "href",
      "https://example.com/download.wav"
    );
    expect(screen.getByRole("link", { name: "View on Freesound" })).toHaveAttribute(
      "href",
      "https://freesound.org/people/kyle/sounds/1/"
    );

    await user.click(screen.getByRole("button", { name: "Export credits" }));
    expect(mockDownloadCredits).toHaveBeenCalledWith([favoriteSound]);

    await user.click(screen.getByRole("button", { name: "Play preview" }));
    expect(mockPlaySound).toHaveBeenCalledWith(favoriteSound);

    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(mockRemoveFavorite).toHaveBeenCalledWith(1);
  });

  it("shows a polished empty state when no favorites are saved", () => {
    mockUseFavorites.mockReturnValue({
      favorites: [],
      removeFavorite: mockRemoveFavorite
    });

    render(
      <MemoryRouter>
        <FavoritesPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Start starring sounds from Search")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export credits" })).toBeDisabled();
    expect(screen.getAllByRole("link", { name: "Browse sound search" })).toHaveLength(2);
  });
});
