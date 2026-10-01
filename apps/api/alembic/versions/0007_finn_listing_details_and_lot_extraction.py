"""finn listing details and lot extraction

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01 02:49:48.913660
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('seller_type', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('published_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('pickup_required', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('capture_method', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('extracted', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('safety_flags', sa.JSON(), nullable=False, server_default='[]'))

    with op.batch_alter_table('lot_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('origin', sa.String(length=12), nullable=False, server_default='manual'))

    with op.batch_alter_table('lots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stated_quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('extraction', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('image_analysis', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lots', schema=None) as batch_op:
        batch_op.drop_column('image_analysis')
        batch_op.drop_column('extraction')
        batch_op.drop_column('stated_quantity')

    with op.batch_alter_table('lot_items', schema=None) as batch_op:
        batch_op.drop_column('origin')

    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_column('safety_flags')
        batch_op.drop_column('extracted')
        batch_op.drop_column('capture_method')
        batch_op.drop_column('pickup_required')
        batch_op.drop_column('published_at')
        batch_op.drop_column('seller_type')
        batch_op.drop_column('location')

