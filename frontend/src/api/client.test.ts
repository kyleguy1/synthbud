import { ApiError, getPlayableUrl, listTags } from "./client";

describe("api client errors", () => {
  it("classifies network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(listTags()).rejects.toMatchObject<ApiError>({
      name: "ApiError",
      kind: "network"
    });
  });

  it("classifies HTTP failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("internal error", {
          status: 500,
          statusText: "Internal Server Error"
        })
      )
    );

    await expect(listTags()).rejects.toMatchObject<ApiError>({
      name: "ApiError",
      kind: "http",
      status: 500
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });
});

describe("getPlayableUrl", () => {
  it("uses provided preview URL when available", () => {
    expect(getPlayableUrl(42, "https://cdn.example.com/p.mp3")).toBe("https://cdn.example.com/p.mp3");
  });

  it("falls back to backend preview proxy route", () => {
    expect(getPlayableUrl(42, null)).toBe("http://localhost:8000/api/sounds/42/preview");
  });
});
