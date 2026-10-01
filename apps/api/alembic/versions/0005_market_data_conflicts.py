"""market data conflicts

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01 02:14:25.380179
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('market_data_conflicts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(length=16), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('detected_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_market_data_conflicts'))
    )
    with op.batch_alter_table('market_data_conflicts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_market_data_conflicts_detected_at'), ['detected_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_data_conflicts_entity_id'), ['entity_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('market_data_conflicts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_market_data_conflicts_entity_id'))
        batch_op.drop_index(batch_op.f('ix_market_data_conflicts_detected_at'))

    op.drop_table('market_data_conflicts')
