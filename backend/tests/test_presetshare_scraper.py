from app.scrapers.presetshare import (
    _parse_list_page,
    _safe_int,
    build_cache_key,
    clear_cache,
)


def test_parse_list_page_extracts_preset_cards():
    html = """
    <div class="preset-card">
      <a href="/p19753">Neuro Lead</a>
      <a href="/presets?instrument=2">Vital</a>
      <a href="/presets?genre=3">Dubstep</a>
      <a href="/presets?type=11">Lead</a>
      <a href="/u/testuser">testuser</a>
      <span class="date">Today</span>
      <span class="likes">12</span>
      <span class="downloads">345</span>
      <span class="comments">6</span>
    </div>
    """

    rows = _parse_list_page(html)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "19753"
    assert row["url"] == "https://presetshare.com/p19753"
    assert row["synth"] == "Vital"
    assert row["synthId"] == 2
    assert row["genreId"] == 3
    assert row["soundTypeId"] == 11
    assert row["likes"] == 12
    assert row["downloads"] == 345
    assert row["comments"] == 6


def test_safe_int_parses_numbers_with_text():
    assert _safe_int("1,204 downloads") == 1204
    assert _safe_int("no data") == 0


def test_cache_key_format_and_clear():
    key = build_cache_key(instrument=2, genre=3, sound_type=11, page=1)
    assert key == "presets:2:3:11:1"
    assert clear_cache("missing-key") == 0

