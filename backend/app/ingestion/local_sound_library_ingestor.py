from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
import hashlib
import re

from app.audio import (
    build_local_waveform_source_key,
    compute_waveform_peaks,
    get_audio_duration_sec,
    load_audio_dependencies,
    load_audio_file_to_array,
)
from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, Sound, SoundFeatures
from app.tag_taxonomy import reconcile_tag_fields


SEPARATOR_RE = re.compile(r"[_\-]+")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LocalSoundDiscovery:
    root: Path
    file_path: Path
    relative_path: Path
    raw_tags: tuple[str, ...]


def _iter_local_files(roots: Iterable[Path]) -> Iterable[tuple[Path, Path]]:
    for root in roots:
        if not root.exists():
            continue
        for file_path in sorted(root.rglob("*")):
            if file_path.is_file():
                yield root, file_path


def _normalize_tag(value: str) -> str:
    compacted = SEPARATOR_RE.sub(" ", value.strip())
    normalized = WHITESPACE_RE.sub(" ", compacted).strip().lower()
    return normalized


def _build_tags(relative_path: Path) -> tuple[str, ...]:
    tags: list[str] = []
    stem_tag = _normalize_tag(relative_path.stem)
    if stem_tag:
        tags.append(stem_tag)

    for part in relative_path.parts[:-1]:
        normalized = _normalize_tag(part)
        if normalized and normalized not in tags:
            tags.append(normalized)

    return tuple(tags)


def classify_local_sound_file(
    root: Path,
    file_path: Path,
    extensions_allowlist: set[str] | None = None,
) -> LocalSoundDiscovery | None:
    extension = file_path.suffix.lower()
    configured_extensions = {value.lower() for value in (extensions_allowlist or set())}
    if configured_extensions and extension not in configured_extensions:
        return None

    relative_path = file_path.resolve().relative_to(root)
    return LocalSoundDiscovery(
        root=root,
        file_path=file_path,
        relative_path=relative_path,
        raw_tags=_build_tags(relative_path),
    )


def _build_source_sound_id(file_path: Path) -> str:
    digest = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()
    return f"local-file:{digest}"


def _load_audio_dependencies():
    try:
        _librosa, _np, sf = load_audio_dependencies()
    except RuntimeError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "Local sample imports require optional audio dependencies. Install backend requirements first."
        ) from exc

    from .feature_extractor import _compute_features

    return sf, _compute_features


def _analyze_audio_file(file_path: Path, target_sr: int, waveform_bins: int) -> tuple[dict, list[float], float]:
    _, compute_features = _load_audio_dependencies()
    data = load_audio_file_to_array(file_path, target_sr)
    return (
        compute_features(data, target_sr),
        compute_waveform_peaks(data, waveform_bins),
        get_audio_duration_sec(data, target_sr),
    )


def _ensure_sound_features_instance(sound: Sound) -> SoundFeatures:
    if sound.features is None:
        sound.features = SoundFeatures(sound_id=sound.id)
    return sound.features


def ingest_local_sounds(limit: int | None = None) -> dict:
    sf, _ = _load_audio_dependencies()
    settings = get_settings()
    roots = [Path(path).expanduser().resolve() for path in settings.sample_local_roots]
    allowlist = {ext.lower() for ext in settings.sample_file_extensions_allowlist}
    target_sr = settings.feature_sample_rate
    waveform_bins = min(256, max(16, settings.waveform_default_bins or 72))

    scanned_files = 0
    ingested = 0
    parsed = 0
    failed = 0
    eligible_files_seen = 0

    with SessionLocal() as db:
        run = IngestionRun(source="sound-local", started_at=datetime.now(UTC))
        db.add(run)
        db.flush()

        try:
            for root, file_path in _iter_local_files(roots):
                scanned_files += 1
                discovery = classify_local_sound_file(root, file_path, allowlist)
                if discovery is None:
                    continue

                eligible_files_seen += 1
                if limit is not None and eligible_files_seen > limit:
                    break

                try:
                    with db.begin_nested():
                        info = sf.info(str(file_path))
                        parsed += 1
                        source_sound_id = _build_source_sound_id(file_path)
                        sound = (
                            db.query(Sound)
                            .filter(Sound.source == "local-filesystem", Sound.source_sound_id == source_sound_id)
                            .first()
                        )
                        if sound is None:
                            sound = Sound(
                                source="local-filesystem",
                                source_sound_id=source_sound_id,
                                name=discovery.relative_path.stem,
                            )
                            db.add(sound)

                        sound.name = discovery.relative_path.stem
                        sound.description = f"Imported from {discovery.relative_path.as_posix()}"
                        raw_tags, canonical_tags = reconcile_tag_fields(raw_tags=discovery.raw_tags)
                        sound.raw_tags = raw_tags
                        sound.tags = canonical_tags
                        sound.duration_sec = float(info.duration) if info.duration else None
                        sound.sample_rate = int(info.samplerate) if info.samplerate else None
                        sound.channels = int(info.channels) if info.channels else None
                        sound.preview_url = None
                        sound.file_url = str(file_path.resolve())
                        sound.source_page_url = None
                        sound.license_url = None
                        sound.license_label = "Local"
                        sound.author = None
                        sound.updated_at = datetime.now(UTC)

                        db.flush()

                        feature_values, waveform_peaks, analyzed_duration_sec = _analyze_audio_file(
                            file_path,
                            target_sr,
                            waveform_bins,
                        )
                        features = _ensure_sound_features_instance(sound)
                        for key, value in feature_values.items():
                            setattr(features, key, value)
                        features.waveform_peaks = waveform_peaks
                        features.waveform_bins = waveform_bins
                        features.waveform_duration_sec = (
                            sound.duration_sec if sound.duration_sec is not None else analyzed_duration_sec
                        )
                        features.waveform_source_key = build_local_waveform_source_key(file_path)
                        features.waveform_analyzed_at = datetime.now(UTC)
                        if sound.duration_sec and 1.0 <= sound.duration_sec <= 16.0:
                            lowered_tags = [tag.lower() for tag in (sound.tags or [])]
                            features.is_loop = "loop" in lowered_tags
                        features.analyzed_at = datetime.now(UTC)
                        ingested += 1
                except Exception:
                    failed += 1
                    continue

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "roots": [str(path) for path in roots],
                "scanned_files": scanned_files,
                "eligible_file_count": eligible_files_seen,
                "parsed_count": parsed,
                "ingested_count": ingested,
                "failed_count": failed,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover - defensive
            db.rollback()
            run = db.get(IngestionRun, run.id)
            if run is None:
                raise
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "roots": [str(path) for path in roots],
                "scanned_files": scanned_files,
                "eligible_file_count": eligible_files_seen,
                "parsed_count": parsed,
                "ingested_count": ingested,
                "failed_count": failed,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "roots": [str(path) for path in roots],
        "scanned_files": scanned_files,
        "eligible_file_count": eligible_files_seen,
        "parsed_count": parsed,
        "ingested_count": ingested,
        "failed_count": failed,
    }


if __name__ == "__main__":
    print(ingest_local_sounds())
