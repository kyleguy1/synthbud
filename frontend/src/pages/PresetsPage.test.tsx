import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PresetsPage } from "./PresetsPage";

const mockListSynths = vi.fn();
const mockListPresetPacks = vi.fn();
const mockListPresetGenres = vi.fn();
const mockListPresetTypes = vi.fn();
const mockListPresets = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listSynths: (...args: unknown[]) => mockListSynths(...args),
    listPresetPacks: (...args: unknown[]) => mockListPresetPacks(...args),
    listPresetGenres: (...args: unknown[]) => mockListPresetGenres(...args),
    listPresetTypes: (...args: unknown[]) => mockListPresetTypes(...args),
    listPresets: (...args: unknown[]) => mockListPresets(...args)
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
    page_size: 20
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
    total: 1,
    page: 1,
    page_size: 20
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
    mockListPresets.mockImplementation(async (filters: { source: string }) =>
      filters.source === "presetshare" ? buildPresetshareResponse() : buildLocalResponse()
    );
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
    expect(mockListPresets).toHaveBeenCalledWith(
      expect.objectContaining({ source: "local-filesystem", pack: "", genre: "", type: "" })
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
    expect(screen.getByPlaceholderText("Search preset names or creators...")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Genre"), "Dubstep");
    await user.selectOptions(screen.getByLabelText("Sound type"), "Lead");

    await waitFor(() => {
      expect(mockListPresets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          source: "presetshare",
          genre: "Dubstep",
          type: "Lead",
          pack: ""
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
  });
});
