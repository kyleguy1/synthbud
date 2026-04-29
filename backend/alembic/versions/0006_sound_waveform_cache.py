from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_sound_waveform_cache"
down_revision: Union[str, None] = "0005_raw_tag_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sound_features", sa.Column("waveform_peaks", sa.JSON(), nullable=True))
    op.add_column("sound_features", sa.Column("waveform_bins", sa.Integer(), nullable=True))
    op.add_column("sound_features", sa.Column("waveform_duration_sec", sa.Float(), nullable=True))
    op.add_column("sound_features", sa.Column("waveform_source_key", sa.Text(), nullable=True))
    op.add_column("sound_features", sa.Column("waveform_analyzed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sound_features", "waveform_analyzed_at")
    op.drop_column("sound_features", "waveform_source_key")
    op.drop_column("sound_features", "waveform_duration_sec")
    op.drop_column("sound_features", "waveform_bins")
    op.drop_column("sound_features", "waveform_peaks")
