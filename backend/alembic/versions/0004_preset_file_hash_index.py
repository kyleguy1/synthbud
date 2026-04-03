from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_preset_file_hash_index"
down_revision: Union[str, None] = "0003_preset_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_preset_files_hash", "preset_files", type_="unique")
    op.create_index(
        "ix_preset_files_hash_sha256",
        "preset_files",
        ["file_hash_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_preset_files_hash_sha256", table_name="preset_files")
    op.create_unique_constraint(
        "uq_preset_files_hash",
        "preset_files",
        ["file_hash_sha256"],
    )
