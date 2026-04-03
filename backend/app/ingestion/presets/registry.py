from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import re

from .base import ParsedPreset
from .serum_parser import parse_serum_preset


PresetParser = Callable[[Path], ParsedPreset]
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class PresetSynthHandler:
    synth_key: str
    display_name: str
    vendor: str | None
    folder_aliases: tuple[str, ...]
    supported_extensions: tuple[str, ...]
    parser: PresetParser

    def matches_folder(self, folder_name: str) -> bool:
        normalized = normalize_synth_folder_name(folder_name)
        aliases = {normalize_synth_folder_name(alias) for alias in self.folder_aliases}
        aliases.add(normalize_synth_folder_name(self.synth_key))
        return normalized in aliases

    def supports_extension(self, extension: str) -> bool:
        return extension.lower() in {value.lower() for value in self.supported_extensions}


def normalize_synth_folder_name(value: str) -> str:
    return NON_ALNUM_RE.sub("", value.strip().lower())


SERUM_HANDLER = PresetSynthHandler(
    synth_key="serum",
    display_name="Serum",
    vendor="Xfer Records",
    folder_aliases=("serum", "xfer-serum", "xfer-records-serum"),
    supported_extensions=(".fxp", ".serumpreset"),
    parser=parse_serum_preset,
)

REGISTERED_SYNTH_HANDLERS: tuple[PresetSynthHandler, ...] = (SERUM_HANDLER,)


def resolve_synth_handler(folder_name: str) -> PresetSynthHandler | None:
    for handler in REGISTERED_SYNTH_HANDLERS:
        if handler.matches_folder(folder_name):
            return handler
    return None
