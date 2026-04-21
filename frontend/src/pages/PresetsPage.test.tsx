import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PresetsPage } from "./PresetsPage";

const mockListSynths = vi.fn();
const mockListPresetPacks = vi.fn();
const mockListPresetGenres = vi.fn();
const mockListPresetTypes = vi.fn();
const mockListPresets = vi.fn();
const mockSyncPresetIndex = vi.fn();
const mockGetLibraryState = vi.fn();
const mockImportPresetLibrary = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listSynths: (...args: unknown[]) => mockListSynths(...args),
    listPresetPacks: (...args: unknown[]) => mockListPresetPacks(...args),
    listPresetGenres: (...args: unknown[]) => mockListPresetGenres(...args),
    listPresetTypes: (...args: unknown[]) => mockListPresetTypes(...args),
    listPresets: (...args: unknown[]) => mockListPresets(...args),
    syncPresetIndex: (...args: unknown[]) => mockSyncPresetIndex(...args),
    getLibraryState: (...args: unknown[]) => mockGetLibraryState(...args),
    importPresetLibrary: (...args: unknown[]) => mockImportPresetLibrary(...args)
  };
});

function buildLocalResponse() {
  return {
    items: [
      {
        id: 1,
        name: "Wide Lead",
        author: "Kyle",
        author_url: null,
        synth_name: "Serum",
        synth_vendor: "Xfer Records",
        tags: ["lead", "wide"],
        visibility: "private" as const,
        is_redistributable: false,
        parse_status: "partial" as const,
        source_url: null,
        source_key: "local-filesystem",
        posted_label: null,
        like_count: null,
        download_count: null,
        comment_count: null,
        pack: {
          id: 2,
          name: "My Bank",
          author: "Kyle",
          synth_name: "Serum",
          synth_vendor: "Xfer Records",
          source_url: null,
          license_label: "Private",
          is_redistributable: false,
          visibility: "private" as const,
          source_key: "local-filesystem"
        }
      }
    ],
    total: 1,
    page: 1,
    page_size: 20,
    has_next: false
  };
}

function buildPresetshareResponse() {
  return {
    items: [
      {
        id: 99,
        name: "Neuro Lead",
        author: "presetuser",
        author_url: "https://presetshare.com/u/presetuser",
        synth_name: "Vital",
        synth_vendor: null,
        tags: ["Dubstep", "Lead"],
        visibility: "public" as const,
        is_redistributable: true,
        parse_status: "success" as const,
        source_url: "https://presetshare.com/p99",
        source_key: "presetshare",
        posted_label: "Today",
        like_count: 10,
        download_count: 200,
        comment_count: 3,
        pack: {
          id: 99,
          name: "Vital Presets",
          author: "presetuser",
          synth_name: "Vital",
          synth_vendor: null,
          source_url: "https://presetshare.com/p99",
          license_label: null,
          is_redistributable: true,
          visibility: "public" as const,
          source_key: "presetshare"
        }
      }
    ],
    total: 2,
    page: 1,
    page_size: 20,
    has_next: true
  };
}

function buildPresetshareIndexResponse() {
  return {
    items: [
      {
        id: 201,
        name: "Indexed Pad",
        author: "cataloguser",
        author_url: "https://presetshare.com/@cataloguser",
        synth_name: "Serum",
        synth_vendor: null,
        tags: ["Synthwave", "Pad"],
        visibility: "public" as const,
        is_redistributable: true,
        parse_status: "partial" as const,
        source_url: "https://presetshare.com/p201",
        source_key: "presetshare-index",
        posted_label: "Yesterday",
        like_count: 3,
        download_count: 44,
        comment_count: 1,
        pack: {
          id: 7,
          name: "Serum Presets",
          author: null,
          synth_name: "Serum",
          synth_vendor: null,
          source_url: "https://presetshare.com",
          license_label: null,
          is_redistributable: true,
          visibility: "public" as const,
          source_key: "presetshare-index"
        }
      }
    ],
    total: 1,
    page: 1,
    page_size: 20,
    has_next: false
  };
}

function buildEmptyResponse() {
  return {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    has_next: false
  };
}

describe("PresetsPage", () => {
  beforeEach(() => {
    mockListSynths.mockImplementation(async (source?: string) =>
      source === "presetshare" ? ["Serum", "Vital"] : ["Serum"]
    );
    mockListPresetPacks.mockResolvedValue(["Factory", "My Bank"]);
    mockListPresetGenres.mockResolvedValue(["Dubstep", "House"]);
    mockListPresetTypes.mockResolvedValue(["Lead", "Pad"]);
    mockGetLibraryState.mockResolvedValue({
      desktop_mode: false,
      sample_roots: [],
      preset_roots: []
    });
    mockListPresets.mockImplementation(async (filters: { source: string; page?: number }) => {
      if (filters.source === "presetshare") {
        return {
          ...buildPresetshareResponse(),
          page: filters.page ?? 1
        };
      }
      if (filters.source === "presetshare-index") {
        return buildPresetshareIndexResponse();
      }
      return buildLocalResponse();
    });
    mockSyncPresetIndex.mockResolvedValue({
      source: "presetshare-index",
      requested_pages: 10,
      scanned_pages: 10,
      ingested_count: 240
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("defaults to local banks and sends pack filters", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText("Search presets, bank, author...")).toBeInTheDocument();
    expect(screen.getByLabelText("Bank")).toBeInTheDocument();
    expect(screen.getByLabelText("Page size")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
    expect(mockListPresets).toHaveBeenCalledWith(
      expect.objectContaining({ source: "local-filesystem", pack: "", genre: "", type: "", sort: "default" })
    );

    await user.selectOptions(screen.getByLabelText("Bank"), "My Bank");

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({ source: "local-filesystem", pack: "My Bank" })
      );
    });
  });

  it("shows remote discovery filters and links for online presets", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Source"), "presetshare");

    await waitFor(() => {
      expect(mockListPresetGenres).toHaveBeenCalledWith("presetshare");
      expect(mockListPresetTypes).toHaveBeenCalledWith("presetshare");
    });

    expect(screen.getByText("Search live presets without importing files first")).toBeInTheDocument();
    expect(screen.queryByLabelText("Bank")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Genre")).toBeInTheDocument();
    expect(screen.getByLabelText("Sound type")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search preset names or creators...")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Sort"), "most-liked");
    await user.selectOptions(screen.getByLabelText("Page size"), "50");
    await user.selectOptions(screen.getByLabelText("Genre"), "Dubstep");
    await user.selectOptions(screen.getByLabelText("Sound type"), "Lead");

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          genre: "Dubstep",
          type: "Lead",
          pack: "",
          sort: "most-liked",
          pageSize: 50
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Neuro Lead")).toBeInTheDocument();
    });
    expect(screen.getByText("Posted Today")).toBeInTheDocument();
    expect(screen.getByText("10 likes")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open preset page" })).toHaveAttribute(
      "href",
      "https://presetshare.com/p99"
    );
    expect(screen.getByRole("link", { name: "View creator" })).toHaveAttribute(
      "href",
      "https://presetshare.com/u/presetuser"
    );

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          page: 2
        })
      );
    });

    await user.click(screen.getByRole("button", { name: "Random preset" }));

    await waitFor(() => {
      expect(screen.getByText("Surprise Pick")).toBeInTheDocument();
    });
  });

  it("refreshes suggestions and applies a new preset mix automatically", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Source"), "presetshare");
    await waitFor(() => {
      expect(screen.getByText("Discovery shortcuts")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Refresh suggestions" }));

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          synth: "Vital",
          genre: "Dubstep",
          type: "Pad",
          sort: "most-liked"
        })
      );
    });
  });

  it("can sync and browse the indexed online preset library", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Source"), "presetshare-index");

    await waitFor(() => {
      expect(screen.getByText("Build a larger searchable preset catalog inside the app")).toBeInTheDocument();
    });

    expect(screen.queryByLabelText("Bank")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Genre")).toBeInTheDocument();
    expect(screen.getByLabelText("Sound type")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sync 10 pages" }));

    await waitFor(() => {
      expect(mockSyncPresetIndex).toHaveBeenCalledWith("presetshare-index", 10);
    });
    await waitFor(() => {
      expect(screen.getByText("Indexed 240 presets from 10 PresetShare pages.")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Indexed Pad")).toBeInTheDocument();
    });
  });

  it("opens live online results from discovery shortcuts when the indexed catalog is empty", async () => {
    const user = userEvent.setup();
    mockListPresets.mockImplementation(async (filters: { source: string; page?: number }) => {
      if (filters.source === "presetshare-index") {
        return buildEmptyResponse();
      }
      if (filters.source === "presetshare") {
        return {
          ...buildPresetshareResponse(),
          page: filters.page ?? 1
        };
      }
      return buildLocalResponse();
    });

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Source"), "presetshare-index");

    await waitFor(() => {
      expect(screen.getByText("No indexed online presets yet. Run a sync to build the searchable catalog.")).toBeInTheDocument();
    });

    const [firstSuggestion] = Array.from(document.querySelectorAll<HTMLButtonElement>(".preset-suggestion-chip"));
    expect(firstSuggestion).toBeTruthy();
    await user.click(firstSuggestion!);

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          sort: "most-liked"
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Neuro Lead")).toBeInTheDocument();
    });
  });

  it("can reset the preset filters back to the defaults", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Source"), "presetshare");

    await waitFor(() => {
      expect(screen.getByText("Search live presets without importing files first")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Synth"), "Vital");
    await user.selectOptions(screen.getByLabelText("Genre"), "Dubstep");
    await user.selectOptions(screen.getByLabelText("Sound type"), "Lead");
    await user.selectOptions(screen.getByLabelText("Sort"), "most-liked");
    await user.selectOptions(screen.getByLabelText("Page size"), "50");

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          synth: "Vital",
          genre: "Dubstep",
          type: "Lead",
          sort: "most-liked",
          pageSize: 50
        })
      );
    });

    await user.click(screen.getByRole("button", { name: "Reset filters" }));

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "local-filesystem",
          q: "",
          synth: "",
          genre: "",
          type: "",
          pack: "",
          visibility: "",
          redistributableOnly: false,
          sort: "default",
          page: 1,
          pageSize: 20
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
      expect(screen.getByLabelText("Bank")).toBeInTheDocument();
    });
  });

  it("imports a local preset folder and refreshes local results", async () => {
    const user = userEvent.setup();
    mockImportPresetLibrary.mockResolvedValue({
      kind: "presets",
      requested_path: "/Users/kylechan/Presets",
      effective_path: "/Users/kylechan/Presets",
      added: true,
      roots: ["/Users/kylechan/Presets"],
      import_result: {
        ingested_count: 5,
        scanned_files: 6,
        parse_failed_count: 1
      }
    });

    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Import preset folder path"), "/Users/kylechan/Presets");
    await user.click(screen.getByRole("button", { name: "Import presets" }));

    await waitFor(() => {
      expect(mockImportPresetLibrary).toHaveBeenCalledWith("/Users/kylechan/Presets");
    });
    await waitFor(() => {
      expect(screen.getByText("5 items indexed · 6 files scanned · 1 skipped.")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(mockListPresets).toHaveBeenCalledTimes(2);
    });
  });
});
