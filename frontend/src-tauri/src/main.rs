use reqwest::blocking::Client;
use serde::Serialize;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

const DEFAULT_API_HOST: &str = "127.0.0.1";
const DEFAULT_API_PORT: u16 = 38080;
const DEFAULT_DB_PORT: u16 = 35432;

struct DesktopState {
    backend_child: Mutex<Option<Child>>,
    runtime: Mutex<Option<BackendRuntime>>,
}

impl Default for DesktopState {
    fn default() -> Self {
        Self {
            backend_child: Mutex::new(None),
            runtime: Mutex::new(None),
        }
    }
}

#[derive(Clone)]
struct BackendRuntime {
    api_base_url: String,
    app_data_dir: PathBuf,
    api_host: String,
    api_port: u16,
    db_port: u16,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeCapabilities {
    external_links: bool,
    save_text_file: bool,
    native_downloads: bool,
    pick_directory: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeConfig {
    api_base_url: String,
    is_desktop: bool,
    capabilities: RuntimeCapabilities,
}

#[tauri::command]
fn get_runtime_config(state: State<'_, DesktopState>) -> Result<RuntimeConfig, String> {
    let runtime = state
        .runtime
        .lock()
        .map_err(|_| "Desktop runtime lock poisoned".to_string())?
        .clone()
        .ok_or_else(|| "Desktop backend runtime is not initialized".to_string())?;

    Ok(RuntimeConfig {
        api_base_url: runtime.api_base_url,
        is_desktop: true,
        capabilities: RuntimeCapabilities {
            external_links: true,
            save_text_file: true,
            native_downloads: false,
            pick_directory: true,
        },
    })
}

#[tauri::command]
fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    app.opener()
        .open_url(url, None::<&str>)
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn save_text_file(
    app: AppHandle,
    default_file_name: String,
    contents: String,
) -> Result<Option<String>, String> {
    let app_for_dialog = app.clone();
    let dialog_name = default_file_name.clone();
    let file_path = tauri::async_runtime::spawn_blocking(move || {
        app_for_dialog
            .dialog()
            .file()
            .set_file_name(dialog_name)
            .blocking_save_file()
    })
    .await
    .map_err(|error| error.to_string())?;

    let Some(file_path) = file_path else {
        return Ok(None);
    };

    let path = file_path
        .into_path()
        .map_err(|_| "Desktop save dialog returned a non-filesystem path".to_string())?;

    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::write(&path, contents).map_err(|error| error.to_string())?;
    Ok(Some(path.display().to_string()))
}

#[tauri::command]
async fn pick_directory(app: AppHandle) -> Result<Option<String>, String> {
    let app_for_dialog = app.clone();
    let folder_path = tauri::async_runtime::spawn_blocking(move || {
        app_for_dialog.dialog().file().blocking_pick_folder()
    })
    .await
    .map_err(|error| error.to_string())?;

    let Some(folder_path) = folder_path else {
        return Ok(None);
    };

    let path = folder_path
        .into_path()
        .map_err(|_| "Desktop folder picker returned a non-filesystem path".to_string())?;

    Ok(Some(path.display().to_string()))
}

fn build_backend_runtime(app: &AppHandle) -> Result<BackendRuntime, String> {
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| error.to_string())?;

    Ok(BackendRuntime {
        api_base_url: format!("http://{}:{}", DEFAULT_API_HOST, DEFAULT_API_PORT),
        app_data_dir,
        api_host: DEFAULT_API_HOST.to_string(),
        api_port: DEFAULT_API_PORT,
        db_port: DEFAULT_DB_PORT,
    })
}

fn build_dev_backend_command(runtime: &BackendRuntime) -> Option<Command> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let frontend_dir = manifest_dir.parent()?.to_path_buf();
    let repo_root = frontend_dir.parent()?.to_path_buf();
    let backend_dir = repo_root.join("backend");
    let python_path = backend_dir.join(".venv").join("bin").join("python");
    if !python_path.exists() {
        return None;
    }

    let mut command = Command::new(python_path);
    command.current_dir(&backend_dir);
    command.arg("-m").arg("app.desktop_launcher");
    configure_backend_command(&mut command, runtime, Some(backend_dir));
    Some(command)
}

fn build_production_backend_command(
    app: &AppHandle,
    runtime: &BackendRuntime,
) -> Result<Command, String> {
    if let Ok(explicit_executable) = env::var("SYNTHBUD_DESKTOP_BACKEND_EXECUTABLE") {
        let mut command = Command::new(explicit_executable);
        configure_backend_command(&mut command, runtime, None);
        return Ok(command);
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| error.to_string())?;
    let candidate = resource_dir.join("bin").join("synthbud-backend");
    if candidate.exists() {
        let mut command = Command::new(candidate);
        // The PyInstaller-frozen backend doesn't need a backend source root —
        // its app/, alembic/, and alembic.ini are unpacked into _MEIPASS at
        // runtime. We pass None to skip setting SYNTHBUD_DESKTOP_BACKEND_ROOT
        // so resolve_backend_roots() falls through to the _MEIPASS branch.
        configure_backend_command(&mut command, runtime, None);
        apply_bundled_postgres_env(&mut command, &resource_dir);
        return Ok(command);
    }

    Err(
        "Unable to locate the packaged backend sidecar. Set SYNTHBUD_DESKTOP_BACKEND_EXECUTABLE or bundle a backend launcher."
            .to_string(),
    )
}

fn apply_bundled_postgres_env(command: &mut Command, resource_dir: &PathBuf) {
    let postgres_bin = resource_dir.join("postgres").join("bin");
    let postgres_lib = resource_dir.join("postgres").join("lib");
    let postgres_share = resource_dir.join("postgres").join("share");

    if postgres_bin.exists() {
        command.env("SYNTHBUD_DESKTOP_POSTGRES_BIN_DIR", &postgres_bin);
    }
    if postgres_share.exists() {
        // Postgres looks for tzdata, locale info, etc. relative to PGSHAREDIR.
        command.env("PGSHAREDIR", &postgres_share);
    }
    if postgres_lib.exists() {
        let existing = env::var("DYLD_LIBRARY_PATH").unwrap_or_default();
        let new_value = if existing.is_empty() {
            postgres_lib.to_string_lossy().into_owned()
        } else {
            format!("{}:{}", postgres_lib.to_string_lossy(), existing)
        };
        command.env("DYLD_LIBRARY_PATH", new_value);
    }
}

fn configure_backend_command(command: &mut Command, runtime: &BackendRuntime, backend_root: Option<PathBuf>) {
    command
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .env("SYNTHBUD_DESKTOP_MODE", "true")
        .env("SYNTHBUD_DESKTOP_APP_DATA_DIR", &runtime.app_data_dir)
        .env("SYNTHBUD_DESKTOP_API_HOST", &runtime.api_host)
        .env("SYNTHBUD_DESKTOP_API_PORT", runtime.api_port.to_string())
        .env("SYNTHBUD_DESKTOP_DB_PORT", runtime.db_port.to_string());

    if let Some(root) = backend_root {
        command.env("SYNTHBUD_DESKTOP_BACKEND_ROOT", root);
    }
}

fn spawn_backend_sidecar(app: &AppHandle, state: &State<'_, DesktopState>) -> Result<BackendRuntime, String> {
    let runtime = build_backend_runtime(app)?;
    fs::create_dir_all(&runtime.app_data_dir).map_err(|error| error.to_string())?;

    let child = if cfg!(debug_assertions) {
        if let Some(mut command) = build_dev_backend_command(&runtime) {
            command.spawn().map_err(|error| error.to_string())?
        } else {
            let mut command = build_production_backend_command(app, &runtime)?;
            command.spawn().map_err(|error| error.to_string())?
        }
    } else {
        let mut command = build_production_backend_command(app, &runtime)?;
        command.spawn().map_err(|error| error.to_string())?
    };

    *state
        .backend_child
        .lock()
        .map_err(|_| "Desktop backend process lock poisoned".to_string())? = Some(child);
    *state
        .runtime
        .lock()
        .map_err(|_| "Desktop runtime lock poisoned".to_string())? = Some(runtime.clone());

    Ok(runtime)
}

fn wait_for_backend_health(runtime: &BackendRuntime) -> Result<(), String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|error| error.to_string())?;
    let health_url = format!("{}/api/health/", runtime.api_base_url);

    for _ in 0..60 {
        let response = client.get(&health_url).send();
        if let Ok(result) = response {
            if result.status().is_success() {
                return Ok(());
            }
        }
        thread::sleep(Duration::from_millis(500));
    }

    Err(format!(
        "Timed out waiting for the synthbud backend to become healthy at {}",
        health_url
    ))
}

fn stop_backend_sidecar(app: &AppHandle) {
    if let Some(state) = app.try_state::<DesktopState>() {
        if let Ok(mut guard) = state.backend_child.lock() {
            if let Some(child) = guard.as_mut() {
                let _ = child.kill();
            }
            *guard = None;
        }
    }
}

fn show_backend_error(app: &AppHandle, message: String) {
    app.dialog()
        .message(message)
        .title("synthbud desktop startup failed")
        .blocking_show();
}

fn main() {
    tauri::Builder::default()
        .manage(DesktopState::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            get_runtime_config,
            open_external_url,
            save_text_file,
            pick_directory
        ])
        .setup(|app| {
            let app_handle = app.handle().clone();
            let main_window = app.get_webview_window("main").expect("missing main window");

            let runtime = spawn_backend_sidecar(&app_handle, &app.state::<DesktopState>())
                .unwrap_or_else(|error| panic!("failed to start synthbud desktop backend: {}", error));

            thread::spawn(move || match wait_for_backend_health(&runtime) {
                Ok(()) => {
                    let _ = main_window.show();
                    let _ = main_window.set_focus();
                }
                Err(error) => {
                    show_backend_error(&app_handle, error);
                    stop_backend_sidecar(&app_handle);
                    app_handle.exit(1);
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if matches!(event, tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit) {
                stop_backend_sidecar(app_handle);
            }
        });
}
