import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.ingestion.local_sound_library_ingestor import ingest_local_sounds
from app.ingestion.presets.local_library_ingestor import ingest_local_presets
from app.ingestion.presets.registry import resolve_synth_handler
from app.schemas import LibraryImportRequest, LibraryImportResponse, LibraryState


router = APIRouter(prefix="/api/libraries", tags=["libraries"])


def _resolve_directory(path_value: str) -> Path:
    resolved = Path(path_value).expanduser().resolve()
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Selected folder does not exist.")
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Selected path must be a folder.")
    return resolved


def _normalize_roots(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        resolved = str(Path(path).expanduser().resolve())
        if resolved not in normalized:
            normalized.append(resolved)
    return normalized


def _normalize_preset_import_root(selected_path: Path) -> Path:
    try:
        child_directories = [child for child in selected_path.iterdir() if child.is_dir()]
    except OSError:
        child_directories = []

    if any(resolve_synth_handler(child.name) for child in child_directories):
        return selected_path

    if resolve_synth_handler(selected_path.name):
        return selected_path.parent

    if resolve_synth_handler(selected_path.parent.name):
        return selected_path.parent.parent

    return selected_path


def _write_desktop_config_root_list(key: str, values: list[str]) -> None:
    settings = get_settings()
    if not settings.desktop_config_path:
        return

    config_path = Path(settings.desktop_config_path)
    if not config_path.exists():
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("paths", {})
    config["paths"][key] = values
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _update_runtime_roots(*, sample_roots: list[str] | None = None, preset_roots: list[str] | None = None) -> None:
    if sample_roots is not None:
        normalized_sample_roots = _normalize_roots(sample_roots)
        os.environ["SYNTHBUD_SAMPLE_LOCAL_ROOTS"] = json.dumps(normalized_sample_roots)
        _write_desktop_config_root_list("sample_local_roots", normalized_sample_roots)
    if preset_roots is not None:
        normalized_preset_roots = _normalize_roots(preset_roots)
        os.environ["SYNTHBUD_PRESET_LOCAL_ROOTS"] = json.dumps(normalized_preset_roots)
        _write_desktop_config_root_list("preset_local_roots", normalized_preset_roots)

    get_settings.cache_clear()


@router.get("/", response_model=LibraryState)
def list_libraries() -> LibraryState:
    settings = get_settings()
    return LibraryState(
        desktop_mode=settings.desktop_mode,
        sample_roots=[str(Path(path).expanduser().resolve()) for path in settings.sample_local_roots],
        preset_roots=[str(Path(path).expanduser().resolve()) for path in settings.preset_local_roots],
    )


@router.post("/samples/import", response_model=LibraryImportResponse)
def import_sample_library(request: LibraryImportRequest) -> LibraryImportResponse:
    settings = get_settings()
    selected_path = _resolve_directory(request.path)
    sample_roots = _normalize_roots([*settings.sample_local_roots, str(selected_path)])
    added = str(selected_path) not in {str(Path(path).expanduser().resolve()) for path in settings.sample_local_roots}
    _update_runtime_roots(sample_roots=sample_roots)
    import_result = ingest_local_sounds()
    updated_settings = get_settings()
    return LibraryImportResponse(
        kind="samples",
        requested_path=request.path,
        effective_path=str(selected_path),
        added=added,
        roots=[str(Path(path).expanduser().resolve()) for path in updated_settings.sample_local_roots],
        import_result=import_result,
    )


@router.post("/presets/import", response_model=LibraryImportResponse)
def import_preset_library(request: LibraryImportRequest) -> LibraryImportResponse:
    settings = get_settings()
    selected_path = _resolve_directory(request.path)
    effective_root = _normalize_preset_import_root(selected_path)
    preset_roots = _normalize_roots([*settings.preset_local_roots, str(effective_root)])
    added = str(effective_root) not in {str(Path(path).expanduser().resolve()) for path in settings.preset_local_roots}
    _update_runtime_roots(preset_roots=preset_roots)
    import_result = ingest_local_presets()
    updated_settings = get_settings()
    return LibraryImportResponse(
        kind="presets",
        requested_path=request.path,
        effective_path=str(effective_root),
        added=added,
        roots=[str(Path(path).expanduser().resolve()) for path in updated_settings.preset_local_roots],
        import_result=import_result,
    )
