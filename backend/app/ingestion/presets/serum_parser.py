from __future__ import annotations

from pathlib import Path
import re

from app.models import PresetParseStatusEnum
from .base import ParsedPreset, looks_like_serum_file


PRINTABLE_STRING_RE = re.compile(rb"[A-Za-z0-9 _\-\.\#]{4,}")
MACRO_NAME_RE = re.compile(r"Macro\s*[1-8]", re.IGNORECASE)


def parse_serum_preset(path: Path) -> ParsedPreset:
    preset_name = path.stem
    if not looks_like_serum_file(path):
        return ParsedPreset(
            preset_name=preset_name,
            synth_name="Unknown",
            parse_status=PresetParseStatusEnum.FAILED,
            parse_error="Unsupported preset format for Serum parser",
        )

    raw_bytes = path.read_bytes()
    string_candidates = [
        blob.decode("utf-8", errors="ignore").strip()
        for blob in PRINTABLE_STRING_RE.findall(raw_bytes)
    ]
    string_candidates = [value for value in string_candidates if value]

    macro_names: list[str] = []
    for value in string_candidates:
        for match in MACRO_NAME_RE.findall(value):
            normalized = match.strip()
            if normalized not in macro_names:
                macro_names.append(normalized)

    osc_count = sum(1 for value in string_candidates if value.lower().startswith("osc"))
    osc_count = osc_count or None

    fx_enabled = True if any("fx" in value.lower() for value in string_candidates) else None
    filter_enabled = (
        True
        if any(value.lower().startswith("filter") for value in string_candidates)
        else None
    )

    parse_status = PresetParseStatusEnum.SUCCESS if macro_names or osc_count else PresetParseStatusEnum.PARTIAL

    return ParsedPreset(
        preset_name=preset_name,
        synth_name="Serum",
        synth_vendor="Xfer Records",
        parse_status=parse_status,
        raw_payload={
            "parser": "serum-mvp-0.1",
            "string_candidates": string_candidates[:200],
        },
        macro_names=macro_names,
        macro_values=None,
        osc_count=osc_count,
        fx_enabled=fx_enabled,
        filter_enabled=filter_enabled,
    )
