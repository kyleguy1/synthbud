from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_preset_schema"
down_revision: Union[str, None] = "0002_ing_status_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    preset_visibility_enum = postgresql.ENUM(
        "private",
        "public",
        name="presetvisibilityenum",
        create_type=False,
    )
    preset_visibility_enum.create(op.get_bind(), checkfirst=True)

    preset_parse_status_enum = postgresql.ENUM(
        "pending",
        "success",
        "partial",
        "failed",
        name="presetparsestatusenum",
        create_type=False,
    )
    preset_parse_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "preset_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "preset_packs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("preset_sources.id"), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("synth_name", sa.String(length=64), nullable=False),
        sa.Column("synth_vendor", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("license_label", sa.String(length=64), nullable=True),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column("is_redistributable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("visibility", preset_visibility_enum, nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_preset_packs_source_external",
        "preset_packs",
        ["source_id", "external_id"],
    )

    op.create_table(
        "presets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pack_id", sa.Integer(), sa.ForeignKey("preset_packs.id"), nullable=False),
        sa.Column("preset_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("synth_name", sa.String(length=64), nullable=False),
        sa.Column("synth_vendor", sa.String(length=64), nullable=True),
        sa.Column("visibility", preset_visibility_enum, nullable=False, server_default="private"),
        sa.Column("is_redistributable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parse_status", preset_parse_status_enum, nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(length=32), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_presets_pack_preset_key",
        "presets",
        ["pack_id", "preset_key"],
    )

    op.create_table(
        "preset_parameters",
        sa.Column(
            "preset_id",
            sa.Integer(),
            sa.ForeignKey("presets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("macro_names", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("macro_values", sa.JSON(), nullable=True),
        sa.Column("osc_count", sa.Integer(), nullable=True),
        sa.Column("fx_enabled", sa.Boolean(), nullable=True),
        sa.Column("filter_enabled", sa.Boolean(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "preset_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("preset_id", sa.Integer(), sa.ForeignKey("presets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("extension", sa.String(length=16), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("is_local", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_preset_files_hash",
        "preset_files",
        ["file_hash_sha256"],
    )

    op.create_index("ix_preset_packs_synth_name", "preset_packs", ["synth_name"])
    op.create_index("ix_presets_synth_name", "presets", ["synth_name"])
    op.create_index("ix_presets_author", "presets", ["author"])
    op.create_index("ix_presets_visibility", "presets", ["visibility"])
    op.create_index("ix_presets_tags", "presets", ["tags"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_presets_tags", table_name="presets")
    op.drop_index("ix_presets_visibility", table_name="presets")
    op.drop_index("ix_presets_author", table_name="presets")
    op.drop_index("ix_presets_synth_name", table_name="presets")
    op.drop_index("ix_preset_packs_synth_name", table_name="preset_packs")

    op.drop_constraint("uq_preset_files_hash", "preset_files", type_="unique")
    op.drop_table("preset_files")
    op.drop_table("preset_parameters")

    op.drop_constraint("uq_presets_pack_preset_key", "presets", type_="unique")
    op.drop_table("presets")

    op.drop_constraint("uq_preset_packs_source_external", "preset_packs", type_="unique")
    op.drop_table("preset_packs")
    op.drop_table("preset_sources")

    preset_parse_status_enum = postgresql.ENUM(
        "pending",
        "success",
        "partial",
        "failed",
        name="presetparsestatusenum",
        create_type=False,
    )
    preset_parse_status_enum.drop(op.get_bind(), checkfirst=True)

    preset_visibility_enum = postgresql.ENUM(
        "private",
        "public",
        name="presetvisibilityenum",
        create_type=False,
    )
    preset_visibility_enum.drop(op.get_bind(), checkfirst=True)
