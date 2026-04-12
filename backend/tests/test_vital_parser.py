from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.presets.vital_parser import parse_vital_preset


def _write_vital(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _full_preset(overrides: dict | None = None) -> dict:
    base = {
        "preset_name": "My Lead",
        "author": "Test Author",
        "synth_version": "1.5.5",
        "comments": "A bright lead",
        "macros": [
            {"name": "Cutoff", "value": 0.8},
            {"name": "Resonance", "value": 0.2},
            {"name": "Attack", "value": 0.0},
            {"name": "Release", "value": 0.5},
        ],
        "settings": {
            "osc_1_on": 1.0,
            "osc_2_on": 1.0,
            "osc_3_on": 0.0,
            "filter_1_on": 1.0,
            "filter_2_on": 0.0,
            "chorus_on": 0.0,
            "delay_on": 1.0,
            "reverb_on": 0.0,
            "distortion_on": 0.0,
            "phaser_on": 0.0,
            "flanger_on": 0.0,
            "compressor_on": 0.0,
        },
    }
    if overrides:
        base.update(overrides)
    return base


# --- Basic extraction ---

def test_extracts_preset_name(tmp_path: Path):
    path = _write_vital(tmp_path, "ignored.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.preset_name == "My Lead"


def test_falls_back_to_filename_when_no_preset_name(tmp_path: Path):
    data = _full_preset({"preset_name": ""})
    path = _write_vital(tmp_path, "Fallback Name.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.preset_name == "Fallback Name"


def test_extracts_author(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.author == "Test Author"


def test_synth_identity(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.synth_name == "Vital"
    assert parsed.synth_vendor == "Matt Tytel"


# --- Macro extraction ---

def test_extracts_macro_names(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.macro_names == ["Cutoff", "Resonance", "Attack", "Release"]


def test_extracts_macro_values(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.macro_values == {
        "Cutoff": 0.8,
        "Resonance": 0.2,
        "Attack": 0.0,
        "Release": 0.5,
    }


def test_empty_macros_list(tmp_path: Path):
    data = _full_preset({"macros": []})
    path = _write_vital(tmp_path, "p.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.macro_names == []
    assert parsed.macro_values is None


# --- Oscillator count ---

def test_osc_count_counts_enabled_oscs(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.osc_count == 2  # osc_1 and osc_2 are on


def test_osc_count_none_when_all_off(tmp_path: Path):
    data = _full_preset()
    data["settings"]["osc_1_on"] = 0.0
    data["settings"]["osc_2_on"] = 0.0
    data["settings"]["osc_3_on"] = 0.0
    path = _write_vital(tmp_path, "p.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.osc_count is None


# --- Filter ---

def test_filter_enabled_when_filter_1_on(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.filter_enabled is True


def test_filter_none_when_both_filters_off(tmp_path: Path):
    data = _full_preset()
    data["settings"]["filter_1_on"] = 0.0
    data["settings"]["filter_2_on"] = 0.0
    path = _write_vital(tmp_path, "p.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.filter_enabled is None


# --- FX ---

def test_fx_enabled_when_delay_on(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.fx_enabled is True


def test_fx_none_when_all_fx_off(tmp_path: Path):
    data = _full_preset()
    for key in ("chorus_on", "delay_on", "reverb_on", "distortion_on", "phaser_on", "flanger_on", "compressor_on"):
        data["settings"][key] = 0.0
    path = _write_vital(tmp_path, "p.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.fx_enabled is None


# --- Parse status ---

def test_success_status_with_macros_and_oscs(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.parse_status.value == "success"


def test_partial_status_with_only_macros(tmp_path: Path):
    data = _full_preset()
    data["settings"]["osc_1_on"] = 0.0
    data["settings"]["osc_2_on"] = 0.0
    data["settings"]["osc_3_on"] = 0.0
    path = _write_vital(tmp_path, "p.vital", data)
    parsed = parse_vital_preset(path)
    assert parsed.parse_status.value == "partial"


def test_failed_status_on_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.vital"
    path.write_text("not json {{{{", encoding="utf-8")
    parsed = parse_vital_preset(path)
    assert parsed.parse_status.value == "failed"
    assert parsed.parse_error is not None


# --- Raw payload ---

def test_raw_payload_contains_parser_key(tmp_path: Path):
    path = _write_vital(tmp_path, "p.vital", _full_preset())
    parsed = parse_vital_preset(path)
    assert parsed.raw_payload is not None
    assert parsed.raw_payload["parser"] == "vital-0.1"
    assert parsed.raw_payload["synth_version"] == "1.5.5"
    assert parsed.raw_payload["comments"] == "A bright lead"
