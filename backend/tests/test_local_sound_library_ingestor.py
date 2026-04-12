from pathlib import Path

from app.ingestion.local_sound_library_ingestor import classify_local_sound_file
from app.tag_taxonomy import reconcile_tag_fields


def test_classify_local_sound_file_builds_raw_tags_and_canonical_tags(tmp_path: Path):
    sample_path = tmp_path / "Drums" / "Warm_Pads" / "Lead-01.wav"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_bytes(b"fake")

    discovery = classify_local_sound_file(tmp_path, sample_path, {".wav"})

    assert discovery is not None
    assert discovery.raw_tags == ("lead 01", "drums", "warm pads")

    raw_tags, canonical_tags = reconcile_tag_fields(raw_tags=discovery.raw_tags)
    assert raw_tags == ["lead 01", "drums", "warm pads"]
    assert canonical_tags == ["drum", "pad", "lead", "warm"]
