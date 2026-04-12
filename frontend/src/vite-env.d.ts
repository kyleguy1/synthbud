/// <reference types="vite/client" />

interface TauriCoreApi {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
}

interface TauriGlobalApi {
  core?: TauriCoreApi;
}

interface Window {
  __TAURI__?: TauriGlobalApi;
}
