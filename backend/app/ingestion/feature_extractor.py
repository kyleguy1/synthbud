from datetime import datetime
from typing import Iterable

import librosa
import numpy as np
import soundfile as sf
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Sound, SoundFeatures


def _download_audio_to_array(url: str, sr: int) -> np.ndarray:
    """
    Download audio from URL and decode to a mono numpy array at target sample rate.
    """
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        audio_bytes = resp.content

    # Decode using soundfile then resample with librosa
    data, original_sr = sf.read(io.BytesIO(audio_bytes))  # type: ignore[name-defined]
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    if original_sr != sr:
        data = librosa.resample(y=data, orig_sr=original_sr, target_sr=sr)
    return data


def _compute_features(y: np.ndarray, sr: int) -> dict:
    """
    Compute basic spectral and loudness-related features.
    """
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


def process_pending_sounds(batch_size: int | None = None) -> None:
    """
    Process sounds that lack analyzed features.

    Downloads previews and computes basic audio features, updating
    the sound_features table.
    """
    settings = get_settings()
    target_sr = settings.feature_sample_rate

    with SessionLocal() as db:
        query = (
            db.query(Sound)
            .outerjoin(SoundFeatures)
            .filter((Sound.features == None) | (SoundFeatures.analyzed_at == None))  # type: ignore[comparison-overlap]
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

                # Simple heuristic for loops
                if sound.duration_sec and 1.0 <= sound.duration_sec <= 16.0:
                    tags = [t.lower() for t in (sound.tags or [])]
                    sf_row.is_loop = "loop" in tags

                sf_row.analyzed_at = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
                continue


if __name__ == "__main__":
    process_pending_sounds()

