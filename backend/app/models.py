from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
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
    raw_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

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


class IngestionStatusEnum(str, enum.Enum):
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
        Enum(
            IngestionStatusEnum,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="ingestionstatusenum",
        ),
        nullable=True,
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class PresetVisibilityEnum(str, enum.Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class PresetParseStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class PresetSource(Base):
    __tablename__ = "preset_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    packs: Mapped[list["PresetPack"]] = relationship("PresetPack", back_populates="source")


class PresetPack(Base):
    __tablename__ = "preset_packs"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_preset_packs_source_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("preset_sources.id"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synth_name: Mapped[str] = mapped_column(String(64), nullable=False)
    synth_vendor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    license_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_redistributable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visibility: Mapped[PresetVisibilityEnum] = mapped_column(
        Enum(
            PresetVisibilityEnum,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="presetvisibilityenum",
        ),
        default=PresetVisibilityEnum.PRIVATE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    source: Mapped[PresetSource] = relationship("PresetSource", back_populates="packs")
    presets: Mapped[list["Preset"]] = relationship(
        "Preset", back_populates="pack", cascade="all, delete-orphan"
    )


class Preset(Base):
    __tablename__ = "presets"
    __table_args__ = (
        UniqueConstraint("pack_id", "preset_key", name="uq_presets_pack_preset_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(Integer, ForeignKey("preset_packs.id"), nullable=False)
    preset_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    raw_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    synth_name: Mapped[str] = mapped_column(String(64), nullable=False)
    synth_vendor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[PresetVisibilityEnum] = mapped_column(
        Enum(
            PresetVisibilityEnum,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="presetvisibilityenum",
        ),
        default=PresetVisibilityEnum.PRIVATE,
        nullable=False,
    )
    is_redistributable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parse_status: Mapped[PresetParseStatusEnum] = mapped_column(
        Enum(
            PresetParseStatusEnum,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="presetparsestatusenum",
        ),
        default=PresetParseStatusEnum.PENDING,
        nullable=False,
    )
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    pack: Mapped[PresetPack] = relationship("PresetPack", back_populates="presets")
    parameters: Mapped[Optional["PresetParameters"]] = relationship(
        "PresetParameters", back_populates="preset", uselist=False, cascade="all, delete-orphan"
    )
    files: Mapped[list["PresetFile"]] = relationship(
        "PresetFile", back_populates="preset", cascade="all, delete-orphan"
    )


class PresetParameters(Base):
    __tablename__ = "preset_parameters"

    preset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("presets.id", ondelete="CASCADE"), primary_key=True
    )
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    macro_names: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    macro_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    osc_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fx_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    filter_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    preset: Mapped[Preset] = relationship("Preset", back_populates="parameters")


class PresetFile(Base):
    __tablename__ = "preset_files"
    __table_args__ = (
        Index("ix_preset_files_hash_sha256", "file_hash_sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("presets.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extension: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_local: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    preset: Mapped[Preset] = relationship("Preset", back_populates="files")
