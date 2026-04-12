from functools import lru_cache
from typing import Dict, List, Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "synthbud-backend"
    environment: str = Field("dev", description="Environment name, e.g. dev/stage/prod")

    # Database
    database_url: str = Field(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/synthbud",
        description="SQLAlchemy database URL for Postgres.",
    )

    # Freesound
    freesound_api_token: str = Field(
        "...",
        description="Freesound API token used for token authentication.",
    )

    # Licensing
    license_allowlist_urls: List[AnyHttpUrl] = Field(
        default_factory=lambda: [
            "https://creativecommons.org/publicdomain/zero/1.0/",  # CC0
            "https://creativecommons.org/licenses/by/4.0/",
            "https://creativecommons.org/licenses/by/3.0/",
        ],
        description="List of license URLs allowed for ingestion.",
    )

    license_label_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "https://creativecommons.org/publicdomain/zero/1.0/": "CC0",
            "https://creativecommons.org/licenses/by/4.0/": "CC-BY",
            "https://creativecommons.org/licenses/by/3.0/": "CC-BY",
        },
        description="Mapping from license URL to normalized label.",
    )

    # Pagination defaults
    default_page_size: int = 20
    max_page_size: int = 100

    # CORS
    cors_allow_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        description="Allowed CORS origins for frontend clients.",
    )

    # Desktop runtime
    desktop_mode: bool = Field(
        False,
        description="Whether the backend is running inside the desktop shell.",
    )
    desktop_app_data_dir: Optional[str] = Field(
        None,
        description="Per-user desktop app data directory managed by the desktop launcher.",
    )
    desktop_config_path: Optional[str] = Field(
        None,
        description="Path to the generated desktop configuration file.",
    )
    desktop_exports_dir: Optional[str] = Field(
        None,
        description="Directory used for desktop-originated exports.",
    )
    desktop_logs_dir: Optional[str] = Field(
        None,
        description="Directory used for desktop runtime logs.",
    )

    # Feature extraction
    feature_sample_rate: int = 22_050
    feature_batch_size: int = 16

    # Preset ingestion
    sample_local_roots: List[str] = Field(
        default_factory=lambda: ["data/samples/local"],
        description="Filesystem roots to scan for local user-owned sample libraries.",
    )
    sample_file_extensions_allowlist: List[str] = Field(
        default_factory=lambda: [".wav", ".aif", ".aiff", ".flac", ".ogg"],
        description="Audio file extensions eligible for local sample library indexing.",
    )
    preset_local_roots: List[str] = Field(
        default_factory=lambda: ["data/presets/local"],
        description="Filesystem roots to scan for local user-owned preset libraries.",
    )
    preset_public_metadata_roots: List[str] = Field(
        default_factory=lambda: ["data/presets/public/metadata"],
        description="Filesystem roots to scan for curated public preset metadata JSON.",
    )
    preset_file_extensions_allowlist: List[str] = Field(
        default_factory=lambda: [".fxp", ".serumpreset", ".vital"],
        description="Preset file extensions eligible for indexing/parsing.",
    )
    preset_public_source_allowlist: List[str] = Field(
        default_factory=lambda: ["github.com", "gumroad.com", "patches.zone"],
        description="Allowlisted domains for public preset metadata sources.",
    )
    enable_private_preset_ingestion: bool = True
    presetshare_base_url: AnyHttpUrl = Field(
        "https://presetshare.com",
        description="Base URL for PresetShare scraper endpoints.",
    )
    presetshare_cache_ttl_seconds: int = Field(
        3600,
        description="Cache TTL in seconds for PresetShare list scrape responses.",
    )
    presetshare_min_request_interval_seconds: float = Field(
        1.0,
        description="Minimum interval between outgoing PresetShare requests.",
    )

    # Patchstorage
    patchstorage_cache_ttl_seconds: int = Field(
        3600,
        description="Cache TTL in seconds for Patchstorage API responses.",
    )
    patchstorage_min_request_interval_seconds: float = Field(
        0.5,
        description="Minimum interval between outgoing Patchstorage API requests.",
    )

    class Config:
        env_prefix = "SYNTHBUD_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
