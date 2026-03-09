import { toSearchParams } from "./query";
import type { SearchFilters } from "../types";

describe("toSearchParams", () => {
  it("includes CC0 license when toggle is enabled", () => {
    const filters: SearchFilters = {
      q: "pluck",
      tags: ["synth"],
      cc0Only: true,
      page: 1,
      pageSize: 20
    };

    const params = toSearchParams(filters);

    expect(params.getAll("license")).toEqual(["CC0"]);
    expect(params.get("q")).toBe("pluck");
    expect(params.getAll("tags")).toEqual(["synth"]);
  });

  it("omits license when CC0 toggle is disabled", () => {
    const filters: SearchFilters = {
      q: "",
      tags: [],
      cc0Only: false,
      page: 1,
      pageSize: 20
    };

    const params = toSearchParams(filters);

    expect(params.getAll("license")).toEqual([]);
  });
});
