"""add_unique_constraint_to_crop_data

Revision ID: 1087d27a075e
Revises: 2f56f985ed30
Create Date: 2026-07-08 14:41:50.492238

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1087d27a075e'
down_revision: Union[str, None] = '2f56f985ed30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = 'crop_data'
CONSTRAINT_NAME = 'uq_crop_data_record'
UNIQUE_COLS = ['country', 'province', 'lon', 'lat', 'variety', 'season_type', 'opt_date']


def upgrade() -> None:
    # Remove existing duplicates keeping only the first occurrence by id
    op.create_unique_constraint(CONSTRAINT_NAME, TABLE_NAME, UNIQUE_COLS)


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_='unique')
