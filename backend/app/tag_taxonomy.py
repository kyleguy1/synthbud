from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TagFacetDefinition:
    key: str
    label: str
    tags: tuple[str, ...]


TAG_FACET_DEFINITIONS: tuple[TagFacetDefinition, ...] = (
    TagFacetDefinition(
        key="family",
        label="Family",
        tags=("synth", "drum", "percussion", "vocal", "fx", "texture", "loop", "one-shot"),
    ),
    TagFacetDefinition(
        key="role",
        label="Role",
        tags=("bass", "kick", "snare", "hat", "clap", "tom", "perc", "pad", "lead", "pluck", "arp", "chord", "keys"),
    ),
    TagFacetDefinition(
        key="timbre",
        label="Timbre",
        tags=("warm", "bright", "dark", "punchy", "wide", "analog", "digital", "distorted", "clean", "lo-fi"),
    ),
    TagFacetDefinition(
        key="mood",
        label="Mood / Style",
        tags=("cinematic", "ambient", "aggressive", "dreamy", "melodic", "atmospheric"),
    ),
    TagFacetDefinition(
        key="genre",
        label="Genre",
        tags=("house", "techno", "trap", "hip-hop", "dubstep", "drum-and-bass", "synthwave"),
    ),
)

TAG_CATEGORY_BY_TAG = {
    tag: definition.key
    for definition in TAG_FACET_DEFINITIONS
    for tag in definition.tags
}
TAG_LABEL_BY_CATEGORY = {definition.key: definition.label for definition in TAG_FACET_DEFINITIONS}
TAG_ORDER = {
    tag: index
    for definition in TAG_FACET_DEFINITIONS
    for index, tag in enumerate(definition.tags)
}
CANONICAL_TAGS = set(TAG_CATEGORY_BY_TAG)
PHRASE_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "synths": ("synth",),
    "serum": ("synth",),
    "vital": ("synth",),
    "surge": ("synth",),
    "surge xt": ("synth",),
    "massive": ("synth",),
    "massive x": ("synth",),
    "sylenth": ("synth",),
    "pigments": ("synth",),
    "drums": ("drum",),
    "drum loops": ("drum", "loop"),
    "percs": ("perc",),
    "percussions": ("percussion",),
    "percussive": ("percussion",),
    "vocals": ("vocal",),
    "vox": ("vocal",),
    "fx": ("fx",),
    "sfx": ("fx",),
    "sound fx": ("fx",),
    "sound effects": ("fx",),
    "textures": ("texture",),
    "loops": ("loop",),
    "one shot": ("one-shot",),
    "one shots": ("one-shot",),
    "oneshot": ("one-shot",),
    "onehots": ("one-shot",),
    "808": ("bass",),
    "basses": ("bass",),
    "kicks": ("kick",),
    "snares": ("snare",),
    "hats": ("hat",),
    "hi hat": ("hat",),
    "hi hats": ("hat",),
    "hihat": ("hat",),
    "hihats": ("hat",),
    "claps": ("clap",),
    "toms": ("tom",),
    "pads": ("pad",),
    "leads": ("lead",),
    "plucks": ("pluck",),
    "arps": ("arp",),
    "chords": ("chord",),
    "keys": ("keys",),
    "warmth": ("warm",),
    "brightness": ("bright",),
    "darker": ("dark",),
    "punch": ("punchy",),
    "punchier": ("punchy",),
    "stereo": ("wide",),
    "analogue": ("analog",),
    "digitals": ("digital",),
    "distortion": ("distorted",),
    "lofi": ("lo-fi",),
    "lo fi": ("lo-fi",),
    "cinema": ("cinematic",),
    "ambience": ("ambient",),
    "atmo": ("atmospheric",),
    "atmos": ("atmospheric",),
    "housey": ("house",),
    "hip hop": ("hip-hop",),
    "hiphop": ("hip-hop",),
    "trapstep": ("trap", "dubstep"),
    "dnb": ("drum-and-bass",),
    "drum n bass": ("drum-and-bass",),
    "drum and bass": ("drum-and-bass",),
    "drum bass": ("drum-and-bass",),
}

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
HASH_RE = re.compile(r"^[a-f0-9]{7,}$")
VERSION_RE = re.compile(r"^v?\d+(?:\.\d+){1,}$")
MEASUREMENT_RE = re.compile(r"^\d+(?:\.\d+)?(?:hz|khz|mhz|bpm|ms|db|kbps|mb|gb|sec|secs|second|seconds)$")
BARE_NUMERIC_RE = re.compile(r"^\d+$")
NOISY_IDENTIFIER_RE = re.compile(r"^(?:id|sample|sound|preset|file)\d+$")


def _normalize_phrase(value: str) -> str:
    return NON_ALNUM_RE.sub(" ", value.strip().lower()).strip()


def _prepare_phrase_aliases() -> None:
    for tag in CANONICAL_TAGS:
        normalized = _normalize_phrase(tag)
        PHRASE_ALIAS_MAP.setdefault(normalized, (tag,))


_prepare_phrase_aliases()


def clean_raw_tags(values: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values or []:
        if value is None:
            continue
        normalized_space = " ".join(value.strip().split())
        if not normalized_space:
            continue
        dedupe_key = normalized_space.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(normalized_space)
    return cleaned


def _is_rejected_token(token: str) -> bool:
    if not token:
        return True
    if token in PHRASE_ALIAS_MAP:
        return False
    if len(token) == 1:
        return True
    if BARE_NUMERIC_RE.fullmatch(token):
        return True
    if MEASUREMENT_RE.fullmatch(token):
        return True
    if TIMESTAMP_RE.fullmatch(token):
        return True
    if VERSION_RE.fullmatch(token):
        return True
    if HASH_RE.fullmatch(token):
        return True
    if NOISY_IDENTIFIER_RE.fullmatch(token):
        return True
    return False


def _canonicalize_phrase(value: str) -> list[str]:
    normalized = _normalize_phrase(value)
    if not normalized:
        return []

    direct = PHRASE_ALIAS_MAP.get(normalized)
    if direct is not None:
        return list(direct)

    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return []

    canonical: list[str] = []
    seen: set[str] = set()
    index = 0
    while index < len(tokens):
        matched = False
        for width in (3, 2, 1):
            if index + width > len(tokens):
                continue
            phrase = " ".join(tokens[index : index + width])
            mapped = PHRASE_ALIAS_MAP.get(phrase)
            if mapped is None:
                continue
            for tag in mapped:
                if tag not in seen:
                    canonical.append(tag)
                    seen.add(tag)
            index += width
            matched = True
            break
        if matched:
            continue

        token = tokens[index]
        if token in CANONICAL_TAGS and token not in seen:
            canonical.append(token)
            seen.add(token)
        elif token in PHRASE_ALIAS_MAP:
            for tag in PHRASE_ALIAS_MAP[token]:
                if tag not in seen:
                    canonical.append(tag)
                    seen.add(tag)
        elif _is_rejected_token(token):
            pass
        index += 1

    return canonical


def sort_canonical_tags(values: Iterable[str]) -> list[str]:
    unique = {value for value in values if value in CANONICAL_TAGS}
    return sorted(
        unique,
        key=lambda tag: (
            next(
                index
                for index, definition in enumerate(TAG_FACET_DEFINITIONS)
                if definition.key == TAG_CATEGORY_BY_TAG[tag]
            ),
            TAG_ORDER[tag],
            tag,
        ),
    )


def canonicalize_tags(values: Iterable[str] | None) -> list[str]:
    canonical: list[str] = []
    seen: set[str] = set()
    for value in clean_raw_tags(values):
        for tag in _canonicalize_phrase(value):
            if tag in CANONICAL_TAGS and tag not in seen:
                canonical.append(tag)
                seen.add(tag)
    return sort_canonical_tags(canonical)


def reconcile_tag_fields(
    *,
    raw_tags: Iterable[str] | None,
    existing_tags: Iterable[str] | None = None,
) -> tuple[list[str] | None, list[str] | None]:
    source_values = raw_tags if raw_tags is not None else existing_tags
    cleaned_raw = clean_raw_tags(source_values)
    canonical = canonicalize_tags(cleaned_raw)
    return (cleaned_raw or None, canonical or None)


def build_tag_facets(values: Iterable[str]) -> list[dict[str, object]]:
    present = set(canonicalize_tags(values))
    facets: list[dict[str, object]] = []
    for definition in TAG_FACET_DEFINITIONS:
        tags = [tag for tag in definition.tags if tag in present]
        facets.append(
            {
                "key": definition.key,
                "label": definition.label,
                "tags": tags,
            }
        )
    return facets


def flatten_tag_facets(facets: Sequence[dict[str, object]]) -> list[str]:
    flattened: list[str] = []
    for facet in facets:
        for tag in facet.get("tags", []):  # type: ignore[union-attr]
            if isinstance(tag, str):
                flattened.append(tag)
    return flattened
