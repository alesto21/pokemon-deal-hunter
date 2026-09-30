"""seller region, landed cost and effective alert level

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01 00:45:27.472134
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seller_country', sa.String(length=2), nullable=True))
        batch_op.add_column(sa.Column('seller_region', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('import_buffer_nok', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('landed_cost_nok', sa.Float(), nullable=True))
        batch_op.create_index(batch_op.f('ix_listings_landed_cost_nok'), ['landed_cost_nok'], unique=False)
        batch_op.create_index(batch_op.f('ix_listings_seller_region'), ['seller_region'], unique=False)

    with op.batch_alter_table('deal_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('alert_level', sa.String(length=16), nullable=True))
        batch_op.create_index(batch_op.f('ix_deal_evaluations_alert_level'), ['alert_level'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('deal_evaluations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deal_evaluations_alert_level'))
        batch_op.drop_column('alert_level')

    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_listings_seller_region'))
        batch_op.drop_index(batch_op.f('ix_listings_landed_cost_nok'))
        batch_op.drop_column('landed_cost_nok')
        batch_op.drop_column('import_buffer_nok')
        batch_op.drop_column('seller_region')
        batch_op.drop_column('seller_country')

