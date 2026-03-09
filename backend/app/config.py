from functools import lru_cache
from typing import Dict, List

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
        default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"],
        description="Allowed CORS origins for frontend clients.",
    )

    # Feature extraction
    feature_sample_rate: int = 22_050
    feature_batch_size: int = 16

    class Config:
        env_prefix = "SYNTHBUD_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
