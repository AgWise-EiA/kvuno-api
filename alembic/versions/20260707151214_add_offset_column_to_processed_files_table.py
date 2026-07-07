"""add_offset_column_to_processed_files_table

Revision ID: 2f56f985ed30
Revises: f608c4212225
Create Date: 2026-07-07 15:12:14.028375

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from app.utils.migration_utils import get_integer_column_type

# revision identifiers, used by Alembic.
revision: str = '2f56f985ed30'
down_revision: Union[str, None] = 'f608c4212225'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('processed_files', sa.Column('offset',get_integer_column_type(), nullable=True))


def downgrade() -> None:
    op.drop_column('processed_files', 'offset')
