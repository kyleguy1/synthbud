from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Sound(Base):
    __tablename__ = "sounds"
    __table_args__ = (
        UniqueConstraint("source", "source_sound_id", name="uq_sounds_source_sound_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_sound_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channels: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    preview_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_page_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    license_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    features: Mapped["SoundFeatures"] = relationship(
        "SoundFeatures", back_populates="sound", uselist=False
    )


class SoundFeatures(Base):
    __tablename__ = "sound_features"

    sound_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sounds.id", ondelete="CASCADE"), primary_key=True
    )

    spectral_centroid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spectral_rolloff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loudness_lufs: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    key: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_loop: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sound: Mapped[Sound] = relationship("Sound", back_populates="features")


class IngestionStatusEnum(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[Optional[IngestionStatusEnum]] = mapped_column(
        Enum(IngestionStatusEnum), nullable=True
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

