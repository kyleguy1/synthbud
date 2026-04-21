from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audio import (
    build_remote_waveform_source_key,
    compute_waveform_peaks,
    get_audio_duration_sec,
    load_audio_dependencies,
    load_audio_url_to_array,
)
from app.config import get_settings
from app.db import SessionLocal
from app.models import Sound, SoundFeatures


def _download_audio_to_array(url: str, sr: int) -> np.ndarray:
    """Download audio from URL and decode to a mono numpy array at target sample rate."""
    return load_audio_url_to_array(url, sr)


def _compute_features(y: np.ndarray, sr: int) -> dict:
    """
    Compute basic spectral and loudness-related features.
    """
    librosa, np, _sf = load_audio_dependencies()
    if y.size == 0:
        return {}

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)

    spectral_centroid = float(np.mean(centroid))
    spectral_rolloff = float(np.mean(rolloff))
    rms_mean = float(np.mean(rms))

    # Approximate LUFS using RMS as a rough proxy
    lufs_approx = 20 * np.log10(max(rms_mean, 1e-9))

    features: dict = {
        "spectral_centroid": spectral_centroid,
        "spectral_rolloff": spectral_rolloff,
        "rms": rms_mean,
        "loudness_lufs": float(lufs_approx),
    }

    # Optional BPM/key estimation for longer samples
    duration_sec = len(y) / sr
    if duration_sec >= 2.0:
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            features["bpm"] = float(tempo)
        except Exception:
            pass
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            pitch_class = int(np.argmax(np.sum(chroma, axis=1)))
            key_labels = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            features["key"] = key_labels[pitch_class]
        except Exception:
            pass

    return features


def _ensure_sound_features_instance(db: Session, sound: Sound) -> SoundFeatures:
    if sound.features is None:
        sound.features = SoundFeatures(sound_id=sound.id)
        db.add(sound.features)
    return sound.features


def _store_waveform(
    features: SoundFeatures,
    *,
    sound: Sound,
    preview_url: str,
    audio: np.ndarray,
    bins: int,
    sample_rate: int,
) -> None:
    features.waveform_peaks = compute_waveform_peaks(audio, bins)
    features.waveform_bins = bins
    features.waveform_duration_sec = sound.duration_sec if sound.duration_sec is not None else get_audio_duration_sec(audio, sample_rate)
    features.waveform_source_key = build_remote_waveform_source_key(preview_url)
    features.waveform_analyzed_at = datetime.now(UTC)


def process_pending_sounds(batch_size: int | None = None) -> None:
    """
    Process sounds that lack analyzed features or cached waveforms.

    Downloads previews and computes audio features plus a default cached
    waveform, updating the sound_features table.
    """
    settings = get_settings()
    target_sr = settings.feature_sample_rate
    waveform_bins = min(256, max(16, settings.waveform_default_bins or 72))

    with SessionLocal() as db:
        query = (
            db.query(Sound)
            .outerjoin(SoundFeatures)
            .filter(  # type: ignore[comparison-overlap]
                or_(
                    Sound.features == None,
                    SoundFeatures.analyzed_at == None,
                    SoundFeatures.waveform_peaks == None,
                    SoundFeatures.waveform_bins != waveform_bins,
                    SoundFeatures.waveform_source_key == None,
                    SoundFeatures.waveform_analyzed_at == None,
                )
            )
            .filter(Sound.preview_url.isnot(None))
            .limit(batch_size or settings.feature_batch_size)
        )

        for sound in query.all():
            if not sound.preview_url:
                continue

            try:
                y = _download_audio_to_array(sound.preview_url, sr=target_sr)
                feats = _compute_features(y, target_sr)
                sf_row = _ensure_sound_features_instance(db, sound)
                for key, value in feats.items():
                    setattr(sf_row, key, value)
                _store_waveform(
                    sf_row,
                    sound=sound,
                    preview_url=sound.preview_url,
                    audio=y,
                    bins=waveform_bins,
                    sample_rate=target_sr,
                )

                analysis_duration_sec = (
                    sound.duration_sec if sound.duration_sec is not None else get_audio_duration_sec(y, target_sr)
                )

                # Simple heuristic for loops
                if analysis_duration_sec and 1.0 <= analysis_duration_sec <= 16.0:
                    tags = [t.lower() for t in (sound.tags or [])]
                    sf_row.is_loop = "loop" in tags

                sf_row.analyzed_at = datetime.now(UTC)
                db.commit()
            except Exception:
                db.rollback()
                continue


if __name__ == "__main__":
    process_pending_sounds()
