from __future__ import annotations

import json
from pathlib import Path

from app.models import PresetParseStatusEnum
from .base import ParsedPreset


_OSC_KEYS = ("osc_1_on", "osc_2_on", "osc_3_on")
_FILTER_KEYS = ("filter_1_on", "filter_2_on")
_FX_KEYS = (
    "chorus_on",
    "compressor_on",
    "delay_on",
    "distortion_on",
    "flanger_on",
    "phaser_on",
    "reverb_on",
)


def parse_vital_preset(path: Path) -> ParsedPreset:
    preset_name = path.stem

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return ParsedPreset(
            preset_name=preset_name,
            synth_name="Vital",
            synth_vendor="Matt Tytel",
            parse_status=PresetParseStatusEnum.FAILED,
            parse_error=f"JSON parse error: {exc}",
        )

    # Vital stores the preset name inside the JSON; fall back to filename
    preset_name = data.get("preset_name") or preset_name
    author: str | None = data.get("author") or None
    synth_version: str | None = data.get("synth_version") or None
    comments: str | None = data.get("comments") or None

    # Macros — Vital has 4, stored as a list of {"name": ..., "value": ...}
    macro_names: list[str] = []
    macro_values: dict[str, float] = {}
    for macro in data.get("macros") or []:
        name = (macro.get("name") or "").strip()
        value = macro.get("value")
        if name:
            macro_names.append(name)
            if value is not None:
                macro_values[name] = float(value)

    # Settings block — oscillator/filter/fx flags are floats where 1.0 = on
    settings: dict = data.get("settings") or {}

    osc_count = sum(
        1 for key in _OSC_KEYS if float(settings.get(key) or 0) > 0.5
    ) or None

    filter_enabled: bool | None = (
        True if any(float(settings.get(k) or 0) > 0.5 for k in _FILTER_KEYS) else None
    )

    fx_enabled: bool | None = (
        True if any(float(settings.get(k) or 0) > 0.5 for k in _FX_KEYS) else None
    )

    has_macros = bool(macro_names)
    has_synth_info = osc_count is not None
    if has_macros and has_synth_info:
        parse_status = PresetParseStatusEnum.SUCCESS
    elif has_macros or has_synth_info:
        parse_status = PresetParseStatusEnum.PARTIAL
    else:
        parse_status = PresetParseStatusEnum.PARTIAL

    return ParsedPreset(
        preset_name=preset_name,
        synth_name="Vital",
        synth_vendor="Matt Tytel",
        author=author,
        parse_status=parse_status,
        raw_payload={
            "parser": "vital-0.1",
            "synth_version": synth_version,
            "comments": comments,
        },
        macro_names=macro_names,
        macro_values=macro_values or None,
        osc_count=osc_count,
        fx_enabled=fx_enabled,
        filter_enabled=filter_enabled,
    )
