from app.ingestion.presets.public_catalog_ingestor import _is_source_allowed


def test_is_source_allowed_accepts_allowlisted_host():
    assert _is_source_allowed("https://github.com/org/repo", {"github.com"})


def test_is_source_allowed_rejects_non_allowlisted_host():
    assert not _is_source_allowed("https://example.org/presets", {"github.com"})

