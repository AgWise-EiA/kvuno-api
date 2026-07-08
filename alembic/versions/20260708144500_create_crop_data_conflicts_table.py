"""create crop_data_conflicts table

Revision ID: 4a5b6c7d8e9f
Revises: 1087d27a075e
Create Date: 2026-07-08 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_utils import get_integer_column_type

# revision identifiers, used by Alembic.
revision: str = '4a5b6c7d8e9f'
down_revision: Union[str, None] = '1087d27a075e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'crop_data_conflicts',
        sa.Column('id', get_integer_column_type(), primary_key=True, autoincrement=True),
        sa.Column('record_data', sa.JSON, nullable=False),
        sa.Column('country', sa.String(20)),
        sa.Column('province', sa.String(20)),
        sa.Column('lon', sa.REAL),
        sa.Column('lat', sa.REAL),
        sa.Column('variety', sa.String(20)),
        sa.Column('season_type', sa.String(20)),
        sa.Column('opt_date', sa.String(8)),
        sa.Column('check_sum', sa.String(100)),
        sa.Column('source', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
    )
    op.create_index('idx_conflict_created_at', 'crop_data_conflicts', ['created_at'])


def downgrade() -> None:
    op.drop_table('crop_data_conflicts')
