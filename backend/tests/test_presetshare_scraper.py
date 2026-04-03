from app.scrapers.presetshare import (
    PRESETSHARE_UPSTREAM_PAGE_SIZE,
    _parse_list_page,
    _safe_int,
    build_cache_key,
    clear_cache,
    scrape_presets_window,
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


def test_parse_list_page_extracts_current_presetshare_markup():
    html = """
    <div class="preset-item">
      <div class="preset-item-content">
        <div class="preset-item-row preset-item-head">
          <a href="/p20256" class="preset-item__name">Dreamy Synth</a>
          <div class="preset-item__info">
            <a class="link-success" href="/presets?instrument=7"><b>Surge</b></a>
            <span class="nobr">&gt; <a class="link-muted" href="/presets?genre=10&instrument=7">Synthwave</a></span>
            <span class="nobr">&gt; <a class="link-muted" href="/presets?type=16&genre=10&instrument=7">Synth</a></span>
          </div>
        </div>
        <div class="preset-item-row preset-item-middle">
          <a class="preset-item-username" href="/@Unrealix">Unrealix</a>
          <span class="text-muted">Today</span>
        </div>
        <div class="preset-item-row preset-item-footer">
          <a class="like-button" href="#">5</a>
          <a class="download-button" href="#">10</a>
          <span>0</span>
        </div>
      </div>
    </div>
    """

    rows = _parse_list_page(html)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "20256"
    assert row["name"] == "Dreamy Synth"
    assert row["url"] == "https://presetshare.com/p20256"
    assert row["synth"] == "Surge"
    assert row["genre"] == "Synthwave"
    assert row["soundType"] == "Synth"
    assert row["author"] == "Unrealix"
    assert row["authorUrl"] == "https://presetshare.com/@Unrealix"
    assert row["datePosted"] == "Today"
    assert row["likes"] == 5
    assert row["downloads"] == 10
    assert row["comments"] == 0


def test_safe_int_parses_numbers_with_text():
    assert _safe_int("1,204 downloads") == 1204
    assert _safe_int("no data") == 0


def test_cache_key_format_and_clear():
    key = build_cache_key(instrument=2, genre=3, sound_type=11, page=1)
    assert key == "presets:2:3:11:1"
    assert clear_cache("missing-key") == 0


def test_scrape_presets_window_can_span_multiple_upstream_pages(monkeypatch):
    pages = {
        1: [{"id": str(index), "name": f"Preset {index}"} for index in range(1, PRESETSHARE_UPSTREAM_PAGE_SIZE + 1)],
        2: [{"id": str(index), "name": f"Preset {index}"} for index in range(25, 49)],
        3: [{"id": str(index), "name": f"Preset {index}"} for index in range(49, 73)],
    }

    monkeypatch.setattr(
        "app.scrapers.presetshare.scrape_presets_page",
        lambda **kwargs: pages.get(kwargs["page"], []),
    )

    rows, has_next = scrape_presets_window(page=2, limit=30)

    assert len(rows) == 30
    assert rows[0]["id"] == "31"
    assert rows[-1]["id"] == "60"
    assert has_next is True
