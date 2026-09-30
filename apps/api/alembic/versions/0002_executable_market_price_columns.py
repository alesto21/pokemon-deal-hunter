"""executable market price columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01 00:26:38.078680
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('price_daily', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cheapest5_median', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('cheapest10_median', sa.Float(), nullable=True))

    with op.batch_alter_table('price_snapshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cheapest3_median', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('cheapest10_median', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('excluded_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('has_expensive_tail', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))



def downgrade() -> None:
    with op.batch_alter_table('price_snapshots', schema=None) as batch_op:
        batch_op.drop_column('has_expensive_tail')
        batch_op.drop_column('excluded_count')
        batch_op.drop_column('cheapest10_median')
        batch_op.drop_column('cheapest3_median')

    with op.batch_alter_table('price_daily', schema=None) as batch_op:
        batch_op.drop_column('cheapest10_median')
        batch_op.drop_column('cheapest5_median')

