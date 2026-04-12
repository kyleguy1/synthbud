from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0005_raw_tag_taxonomy"
down_revision: Union[str, None] = "0004_preset_file_hash_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sounds", sa.Column("raw_tags", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("presets", sa.Column("raw_tags", postgresql.ARRAY(sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("presets", "raw_tags")
    op.drop_column("sounds", "raw_tags")
