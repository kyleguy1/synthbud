import { ApiError, listTags } from "./client";

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
