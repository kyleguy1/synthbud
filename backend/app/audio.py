from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Sequence

import httpx


def load_audio_dependencies():
    try:
        import librosa
        import numpy as np
        import soundfile as sf
    except ModuleNotFoundError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "Audio analysis requires optional audio dependencies. Install backend requirements first."
        ) from exc

    return librosa, np, sf


def _coerce_audio_array(data: Any, *, original_sr: int, target_sr: int):
    librosa, np, _sf = load_audio_dependencies()

    if isinstance(data, np.ndarray) and data.ndim > 1:
        data = np.mean(data, axis=1)
    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=np.float32)
    else:
        data = data.astype(np.float32, copy=False)

    if original_sr != target_sr:
        data = librosa.resample(y=data, orig_sr=original_sr, target_sr=target_sr)

    return data.astype(np.float32, copy=False)


def load_audio_url_to_array(url: str, target_sr: int):
    _librosa, _np, sf = load_audio_dependencies()

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    data, original_sr = sf.read(io.BytesIO(response.content), dtype="float32", always_2d=False)
    return _coerce_audio_array(data, original_sr=original_sr, target_sr=target_sr)


def load_audio_file_to_array(file_path: Path, target_sr: int):
    _librosa, _np, sf = load_audio_dependencies()

    data, original_sr = sf.read(str(file_path), dtype="float32", always_2d=False)
    return _coerce_audio_array(data, original_sr=original_sr, target_sr=target_sr)


def compute_waveform_peaks(audio, bins: int) -> list[float]:
    if bins <= 0:
        raise ValueError("bins must be positive")

    _librosa, np, _sf = load_audio_dependencies()

    if not isinstance(audio, np.ndarray):
        audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    magnitudes = np.abs(audio.astype(np.float32, copy=False))
    if magnitudes.size == 0:
        return [0.0] * bins

    edges = np.linspace(0, magnitudes.size, num=bins + 1, dtype=int)
    peaks: list[float] = []
    for index in range(bins):
        start = int(edges[index])
        end = int(edges[index + 1])
        segment = magnitudes[start:end] if end > start else magnitudes[start : start + 1]
        peaks.append(float(np.max(segment)) if segment.size else 0.0)

    max_peak = max(peaks, default=0.0)
    if max_peak <= 0:
        return [0.0] * bins

    return [round(peak / max_peak, 6) for peak in peaks]


def get_audio_duration_sec(audio, sample_rate: int) -> float:
    if sample_rate <= 0:
        return 0.0

    if hasattr(audio, "shape"):
        sample_count = int(audio.shape[0])
    else:
        sample_count = len(audio)

    return float(sample_count / sample_rate)


def build_local_waveform_source_key(file_path: Path) -> str:
    resolved_path = file_path.expanduser().resolve()
    stat = resolved_path.stat()
    return f"local:{resolved_path}:{stat.st_mtime_ns}:{stat.st_size}"


def build_remote_waveform_source_key(preview_url: str) -> str:
    return f"remote:{preview_url.strip()}"


def resample_waveform_peaks(peaks: Sequence[float], bins: int) -> list[float]:
    if bins <= 0:
        raise ValueError("bins must be positive")

    normalized = [float(max(0.0, min(1.0, peak))) for peak in peaks]
    if not normalized:
        return [0.0] * bins

    if len(normalized) == bins:
        return [round(peak, 6) for peak in normalized]

    if bins == 1:
        return [round(max(normalized), 6)]

    if len(normalized) == 1:
        return [round(normalized[0], 6)] * bins

    source_count = len(normalized)
    if bins < source_count:
        resampled: list[float] = []
        for index in range(bins):
            start = math.floor(index * source_count / bins)
            end = math.ceil((index + 1) * source_count / bins)
            segment = normalized[start:max(start + 1, end)]
            resampled.append(round(max(segment, default=0.0), 6))
        return resampled

    scale = (source_count - 1) / (bins - 1)
    expanded: list[float] = []
    for index in range(bins):
        position = index * scale
        left = math.floor(position)
        right = min(source_count - 1, math.ceil(position))
        if left == right:
            expanded.append(round(normalized[left], 6))
            continue

        ratio = position - left
        value = normalized[left] + (normalized[right] - normalized[left]) * ratio
        expanded.append(round(value, 6))

    return expanded
