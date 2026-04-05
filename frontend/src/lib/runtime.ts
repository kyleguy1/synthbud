import type { RuntimeConfig } from "../types";

const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  isDesktop: false,
  capabilities: {
    externalLinks: false,
    saveTextFile: false,
    nativeDownloads: false,
    pickDirectory: false
  }
};

interface TauriCoreApi {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
}

interface TauriGlobal {
  core?: TauriCoreApi;
}

let cachedRuntimeConfig: RuntimeConfig = DEFAULT_RUNTIME_CONFIG;
let runtimeConfigPromise: Promise<RuntimeConfig> | null = null;

function getTauriGlobal(): TauriGlobal | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  return window.__TAURI__;
}

function getTauriInvoke(): TauriCoreApi["invoke"] | null {
  return getTauriGlobal()?.core?.invoke ?? null;
}

export function getDefaultRuntimeConfig(): RuntimeConfig {
  return DEFAULT_RUNTIME_CONFIG;
}

export function isDesktopRuntime(): boolean {
  return Boolean(getTauriInvoke()) || cachedRuntimeConfig.isDesktop;
}

export function getRuntimeConfig(): RuntimeConfig {
  return cachedRuntimeConfig;
}

export function getApiBaseUrl(): string {
  return cachedRuntimeConfig.apiBaseUrl;
}

export async function initializeRuntimeConfig(): Promise<RuntimeConfig> {
  if (runtimeConfigPromise) {
    return runtimeConfigPromise;
  }

  const invoke = getTauriInvoke();
  if (!invoke) {
    cachedRuntimeConfig = DEFAULT_RUNTIME_CONFIG;
    runtimeConfigPromise = Promise.resolve(cachedRuntimeConfig);
    return runtimeConfigPromise;
  }

  runtimeConfigPromise = invoke<RuntimeConfig>("get_runtime_config")
    .then((config) => {
      cachedRuntimeConfig = config;
      return cachedRuntimeConfig;
    })
    .catch(() => {
      cachedRuntimeConfig = DEFAULT_RUNTIME_CONFIG;
      return cachedRuntimeConfig;
    });

  return runtimeConfigPromise;
}

export async function openExternalUrl(url: string): Promise<void> {
  const invoke = getTauriInvoke();
  if (invoke) {
    await invoke("open_external_url", { url });
    return;
  }

  if (typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

export async function saveTextFile(
  defaultFileName: string,
  contents: string
): Promise<string | null> {
  const invoke = getTauriInvoke();
  if (invoke) {
    return invoke<string | null>("save_text_file", { defaultFileName, contents });
  }

  const blob = new Blob([contents], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = defaultFileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return null;
}

export async function pickDirectory(): Promise<string | null> {
  const invoke = getTauriInvoke();
  if (!invoke) {
    return null;
  }

  return invoke<string | null>("pick_directory");
}

export function resetRuntimeConfigForTests(): void {
  cachedRuntimeConfig = DEFAULT_RUNTIME_CONFIG;
  runtimeConfigPromise = null;
}
