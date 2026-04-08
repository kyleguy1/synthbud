import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SearchPage } from "./SearchPage";
import { ApiError } from "../api/client";

const mockListSounds = vi.fn();
const mockListTagFacets = vi.fn();
const mockGetLibraryState = vi.fn();
const mockImportSampleLibrary = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listSounds: (...args: unknown[]) => mockListSounds(...args),
    listTagFacets: (...args: unknown[]) => mockListTagFacets(...args),
    getLibraryState: (...args: unknown[]) => mockGetLibraryState(...args),
    importSampleLibrary: (...args: unknown[]) => mockImportSampleLibrary(...args)
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
    mockListTagFacets.mockResolvedValue([]);
    mockGetLibraryState.mockResolvedValue({
      desktop_mode: false,
      sample_roots: [],
      preset_roots: []
    });
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

  it("passes duration, brightness, and bpm filters into the sounds request", async () => {
    const user = userEvent.setup();
    mockListSounds.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20
    });

    renderWithRouter();

    await waitFor(() => {
      expect(mockListSounds).toHaveBeenCalled();
    });

    mockListSounds.mockClear();

    const [
      minDurationInput,
      maxDurationInput,
      minBrightnessInput,
      maxBrightnessInput,
      minBpmInput,
      maxBpmInput
    ] = screen.getAllByRole("spinbutton");

    await user.type(minDurationInput, "5");
    await user.type(maxDurationInput, "12");

    await user.type(minBrightnessInput, "3200");
    await user.type(maxBrightnessInput, "5600");
    await user.type(minBpmInput, "90");
    await user.type(maxBpmInput, "128");

    await waitFor(() => {
      expect(mockListSounds).toHaveBeenLastCalledWith(
        expect.objectContaining({
          minDuration: 5,
          maxDuration: 12,
          minBrightness: 3200,
          maxBrightness: 5600,
          bpmMin: 90,
          bpmMax: 128
        })
      );
    });
  });

  it("imports a local sample folder and refreshes search data", async () => {
    const user = userEvent.setup();
    mockListSounds.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20
    });
    mockImportSampleLibrary.mockResolvedValue({
      kind: "samples",
      requested_path: "/Users/kylechan/Samples",
      effective_path: "/Users/kylechan/Samples",
      added: true,
      roots: ["/Users/kylechan/Samples"],
      import_result: {
        ingested_count: 8,
        scanned_files: 10,
        failed_count: 1
      }
    });

    renderWithRouter();

    await waitFor(() => {
      expect(mockListSounds).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByLabelText("Import sample library path"), "/Users/kylechan/Samples");
    await user.click(screen.getByRole("button", { name: "Import samples" }));

    await waitFor(() => {
      expect(mockImportSampleLibrary).toHaveBeenCalledWith("/Users/kylechan/Samples");
    });
    await waitFor(() => {
      expect(screen.getByText("8 items indexed · 10 files scanned · 1 skipped.")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(mockListSounds).toHaveBeenCalledTimes(2);
    });
  });

  it("renders grouped canonical tag facets and hides obscure raw tags", async () => {
    mockListSounds.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20
    });
    mockListTagFacets.mockResolvedValue([
      { key: "role", label: "Role", tags: ["pad", "lead"] },
      { key: "timbre", label: "Timbre", tags: ["warm", "lo-fi"] }
    ]);

    renderWithRouter();

    expect(await screen.findByRole("heading", { name: "Role" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pad" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lo-Fi" })).toBeInTheDocument();
    expect(screen.queryByText("232hz")).not.toBeInTheDocument();
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
