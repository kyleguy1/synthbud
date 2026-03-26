from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0002_ing_status_fix"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'ingestionstatusenum'
            ) THEN
                CREATE TYPE ingestionstatusenum AS ENUM ('running', 'success', 'error');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE ingestion_runs
        ADD COLUMN IF NOT EXISTS status ingestionstatusenum;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ingestion_runs
        DROP COLUMN IF EXISTS status;
        """
    )
