import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PresetsPage } from "./PresetsPage";

const mockListSynths = vi.fn();
const mockListPresets = vi.fn();

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    listSynths: (...args: unknown[]) => mockListSynths(...args),
    listPresets: (...args: unknown[]) => mockListPresets(...args)
  };
});

describe("PresetsPage", () => {
  beforeEach(() => {
    mockListSynths.mockResolvedValue(["Serum"]);
    mockListPresets.mockResolvedValue({
      items: [
        {
          id: 1,
          name: "Wide Lead",
          author: "Kyle",
          synth_name: "Serum",
          synth_vendor: "Xfer Records",
          tags: ["lead", "wide"],
          visibility: "private",
          is_redistributable: false,
          parse_status: "partial",
          source_url: null,
          pack: {
            id: 2,
            name: "My Bank",
            author: "Kyle",
            synth_name: "Serum",
            synth_vendor: "Xfer Records",
            source_url: null,
            license_label: "Private",
            is_redistributable: false,
            visibility: "private"
          }
        }
      ],
      total: 1,
      page: 1,
      page_size: 20
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders loaded preset cards", async () => {
    render(
      <MemoryRouter>
        <PresetsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Wide Lead")).toBeInTheDocument();
    });
    expect(screen.getByText("My Bank")).toBeInTheDocument();
    expect(screen.getAllByText("Serum").length).toBeGreaterThan(0);
  });
});

