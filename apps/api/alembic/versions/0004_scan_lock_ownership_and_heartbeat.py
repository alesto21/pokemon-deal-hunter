"""scan lock ownership and heartbeat

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01 01:01:24.691367
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('source_status', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lock_owner', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('lock_heartbeat_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('next_run_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('source_status', schema=None) as batch_op:
        batch_op.drop_column('next_run_at')
        batch_op.drop_column('lock_heartbeat_at')
        batch_op.drop_column('lock_owner')

