from datetime import datetime
from typing import List, Optional, TypeVar, Generic

from pydantic import BaseModel, ConfigDict


class SoundFeatures(BaseModel):
    spectral_centroid: Optional[float] = None
    spectral_rolloff: Optional[float] = None
    loudness_lufs: Optional[float] = None
    rms: Optional[float] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    is_loop: Optional[bool] = None


class SoundSummary(BaseModel):
    id: int
    name: str
    author: Optional[str] = None
    duration_sec: Optional[float] = None
    tags: List[str] = []
    license_label: Optional[str] = None
    preview_url: Optional[str] = None
    file_url: Optional[str] = None
    source_page_url: Optional[str] = None
    can_preview: bool = False
    can_download: bool = False
    brightness: Optional[float] = None
    bpm: Optional[float] = None
    key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SoundDetail(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    author: Optional[str] = None
    duration_sec: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    tags: List[str] = []
    license_url: Optional[str] = None
    license_label: Optional[str] = None
    source: str
    source_sound_id: str
    source_page_url: Optional[str] = None
    preview_url: Optional[str] = None
    file_url: Optional[str] = None
    ingested_at: datetime
    updated_at: datetime
    features: Optional[SoundFeatures] = None

    model_config = ConfigDict(from_attributes=True)


class PresetPackSummary(BaseModel):
    id: int
    name: str
    author: Optional[str] = None
    synth_name: str
    synth_vendor: Optional[str] = None
    source_url: Optional[str] = None
    license_label: Optional[str] = None
    is_redistributable: bool = False
    visibility: str
    source_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PresetSummary(BaseModel):
    id: int
    name: str
    author: Optional[str] = None
    author_url: Optional[str] = None
    synth_name: str
    synth_vendor: Optional[str] = None
    tags: List[str] = []
    visibility: str
    is_redistributable: bool = False
    parse_status: str
    source_url: Optional[str] = None
    source_key: Optional[str] = None
    posted_label: Optional[str] = None
    like_count: Optional[int] = None
    download_count: Optional[int] = None
    comment_count: Optional[int] = None
    pack: PresetPackSummary

    model_config = ConfigDict(from_attributes=True)


class PresetDetail(PresetSummary):
    parse_error: Optional[str] = None
    parser_version: Optional[str] = None
    imported_at: datetime
    updated_at: datetime
    raw_payload: Optional[dict] = None
    macro_names: List[str] = []
    macro_values: Optional[dict] = None
    osc_count: Optional[int] = None
    fx_enabled: Optional[bool] = None
    filter_enabled: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
