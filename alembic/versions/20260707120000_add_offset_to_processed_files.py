"""add offset column to processed_files

Revision ID: 20260707120000
Revises: 20240813155554
Create Date: 2026-07-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260707120000'
down_revision: Union[str, None] = '20240813155554'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('processed_files', sa.Column('offset', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('processed_files', 'offset')
