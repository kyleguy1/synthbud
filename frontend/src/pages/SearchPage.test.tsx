import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SearchPage } from "./SearchPage";
import { ApiError } from "../api/client";

const mockListSounds = vi.fn();
const mockListTags = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listSounds: (...args: unknown[]) => mockListSounds(...args),
    listTags: (...args: unknown[]) => mockListTags(...args)
  };
});

vi.mock("../state/FavoritesContext", () => ({
  useFavorites: () => ({
    toggleFromSummary: vi.fn(),
    isFavoriteSound: () => false
  })
}));

vi.mock("../state/PlayerContext", () => ({
  usePlayer: () => ({
    state: { sound: null, isPlaying: false, currentTime: 0, duration: 0, error: null },
    playSound: vi.fn(),
    togglePlayPause: vi.fn()
  })
}));

describe("SearchPage states", () => {
  beforeEach(() => {
    mockListTags.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a friendly message for network failures", async () => {
    mockListSounds.mockRejectedValue(
      new ApiError(
        "network",
        "We couldn't load data right now. Please try again in a moment.",
        "http://localhost:8000/api/sounds/"
      )
    );

    renderWithRouter();

    expect(await screen.findByText(/We couldn't load sounds right now/i)).toBeInTheDocument();
    expect(screen.queryByText(/Backend unreachable/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/api\/health/i)).not.toBeInTheDocument();
  });

  it("shows empty state when request succeeds with no sounds", async () => {
    mockListSounds.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20
    });

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText(/No sounds found for current filters/i)).toBeInTheDocument();
    });
  });
});

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<SearchPage />} />
      </Routes>
    </MemoryRouter>
  );
}
