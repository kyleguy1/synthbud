from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sounds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_sound_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("source_page_url", sa.Text(), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("license_label", sa.String(length=32), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_sounds_source_sound_id", "sounds", ["source", "source_sound_id"]
    )

    op.create_table(
        "sound_features",
        sa.Column(
            "sound_id",
            sa.Integer(),
            sa.ForeignKey("sounds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("spectral_centroid", sa.Float(), nullable=True),
        sa.Column("spectral_rolloff", sa.Float(), nullable=True),
        sa.Column("loudness_lufs", sa.Float(), nullable=True),
        sa.Column("rms", sa.Float(), nullable=True),
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("key", sa.String(length=16), nullable=True),
        sa.Column("is_loop", sa.Boolean(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )

    ingestion_status_enum = postgresql.ENUM(
        "running",
        "success",
        "error",
        name="ingestionstatusenum",
        create_type=False,
    )
    ingestion_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", ingestion_status_enum, nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
    )

    # Indexes
    op.create_index(
        "ix_sounds_tags",
        "sounds",
        ["tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_sounds_duration",
        "sounds",
        ["duration_sec"],
    )
    op.create_index(
        "ix_sounds_license_label",
        "sounds",
        ["license_label"],
    )
    op.create_index(
        "ix_sounds_author",
        "sounds",
        ["author"],
    )
    op.create_index(
        "ix_sound_features_spectral_centroid",
        "sound_features",
        ["spectral_centroid"],
    )
    op.create_index(
        "ix_sound_features_bpm",
        "sound_features",
        ["bpm"],
    )
    op.create_index(
        "ix_sound_features_key",
        "sound_features",
        ["key"],
    )


def downgrade() -> None:
    op.drop_index("ix_sound_features_key", table_name="sound_features")
    op.drop_index("ix_sound_features_bpm", table_name="sound_features")
    op.drop_index("ix_sound_features_spectral_centroid", table_name="sound_features")
    op.drop_index("ix_sounds_author", table_name="sounds")
    op.drop_index("ix_sounds_license_label", table_name="sounds")
    op.drop_index("ix_sounds_duration", table_name="sounds")
    op.drop_index("ix_sounds_tags", table_name="sounds")

    op.drop_table("ingestion_runs")
    ingestion_status_enum = postgresql.ENUM(
        "running",
        "success",
        "error",
        name="ingestionstatusenum",
        create_type=False,
    )
    ingestion_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table("sound_features")
    op.drop_constraint(
        "uq_sounds_source_sound_id", table_name="sounds", type_="unique"
    )
    op.drop_table("sounds")
