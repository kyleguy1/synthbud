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
    playSound: vi.fn()
  })
}));

describe("SearchPage states", () => {
  beforeEach(() => {
    mockListTags.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows actionable backend hint for network failures", async () => {
    mockListSounds.mockRejectedValue(
      new ApiError(
        "network",
        "Backend unreachable at http://localhost:8000. Check http://localhost:8000/api/health/.",
        "http://localhost:8000/api/sounds/"
      )
    );

    renderWithRouter();

    expect(await screen.findByText(/Backend unreachable at http:\/\/localhost:8000/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/Verify http:\/\/localhost:8000\/api\/health\//i)
    ).toBeInTheDocument();
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
