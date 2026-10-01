"""landed cost basis and seller quotes

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01 02:33:27.240620
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('seller_shipping_quotes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('seller', sa.String(length=200), nullable=False),
    sa.Column('seller_external_id', sa.String(length=64), nullable=True),
    sa.Column('route', sa.String(length=12), nullable=False),
    sa.Column('destination', sa.String(length=2), nullable=False),
    sa.Column('shipment_nok', sa.Float(), nullable=False),
    sa.Column('fees_nok', sa.Float(), nullable=True),
    sa.Column('capacity_items', sa.Integer(), nullable=True),
    sa.Column('observed_amounts', sa.JSON(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('observed_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seller_shipping_quotes')),
    sa.UniqueConstraint('source', 'seller', 'route', 'destination', name='uq_seller_quote')
    )
    with op.batch_alter_table('seller_shipping_quotes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_seller_shipping_quotes_seller_external_id'), ['seller_external_id'], unique=False)

    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fees_nok', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('shipping_basis', sa.String(length=12), nullable=False, server_default='estimated'))
        batch_op.add_column(sa.Column('fees_basis', sa.String(length=12), nullable=False, server_default='exact'))
        batch_op.add_column(sa.Column('landed_cost_confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('purchase_route', sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column('seller_external_id', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_listings_seller_external_id'), ['seller_external_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('listings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_listings_seller_external_id'))
        batch_op.drop_column('seller_external_id')
        batch_op.drop_column('purchase_route')
        batch_op.drop_column('landed_cost_confidence')
        batch_op.drop_column('fees_basis')
        batch_op.drop_column('shipping_basis')
        batch_op.drop_column('fees_nok')

    with op.batch_alter_table('seller_shipping_quotes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_seller_shipping_quotes_seller_external_id'))

    op.drop_table('seller_shipping_quotes')
