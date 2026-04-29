import { ApiError, getPlayableUrl, getSoundWaveform, listTags } from "./client";

describe("api client errors", () => {
  it("classifies network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(listTags()).rejects.toMatchObject({
      name: "ApiError",
      kind: "network",
      message: "We couldn't load data right now. Please try again in a moment."
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

    await expect(listTags()).rejects.toMatchObject({
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

describe("getSoundWaveform", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests waveform data for a sound and bin count", async () => {
    const response = {
      sound_id: 42,
      bins: 96,
      duration_sec: 1.2,
      peaks: [0.1, 0.4, 0.6]
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(getSoundWaveform(42, 96)).resolves.toEqual(response);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sounds/42/waveform?bins=96", undefined);
  });
});
