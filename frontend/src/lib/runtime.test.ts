import {
  getApiBaseUrl,
  getDefaultRuntimeConfig,
  getRuntimeConfig,
  initializeRuntimeConfig,
  openExternalUrl,
  pickDirectory,
  resetRuntimeConfigForTests
} from "./runtime";

describe("runtime config", () => {
  afterEach(() => {
    resetRuntimeConfigForTests();
    delete window.__TAURI__;
    vi.restoreAllMocks();
  });

  it("defaults to the web runtime configuration", async () => {
    const config = await initializeRuntimeConfig();

    expect(config).toEqual(getDefaultRuntimeConfig());
    expect(getRuntimeConfig().isDesktop).toBe(false);
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("hydrates desktop runtime config through Tauri invoke", async () => {
    const invoke = vi.fn().mockResolvedValue({
      apiBaseUrl: "http://127.0.0.1:38080",
      isDesktop: true,
      capabilities: {
        externalLinks: true,
        saveTextFile: true,
        nativeDownloads: false,
        pickDirectory: true
      }
    });
    window.__TAURI__ = { core: { invoke } };

    const config = await initializeRuntimeConfig();

    expect(invoke).toHaveBeenCalledWith("get_runtime_config");
    expect(config.isDesktop).toBe(true);
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:38080");
  });

  it("uses the desktop picker when available", async () => {
    const invoke = vi
      .fn()
      .mockResolvedValueOnce({
        apiBaseUrl: "http://127.0.0.1:38080",
        isDesktop: true,
        capabilities: {
          externalLinks: true,
          saveTextFile: true,
          nativeDownloads: false,
          pickDirectory: true
        }
      })
      .mockResolvedValueOnce("/Users/example/Samples");

    window.__TAURI__ = { core: { invoke } };
    await initializeRuntimeConfig();

    await expect(pickDirectory()).resolves.toBe("/Users/example/Samples");
    expect(invoke).toHaveBeenLastCalledWith("pick_directory");
  });

  it("falls back to window.open in the browser", async () => {
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    await openExternalUrl("https://example.com");

    expect(openSpy).toHaveBeenCalledWith("https://example.com", "_blank", "noopener,noreferrer");
  });
});
