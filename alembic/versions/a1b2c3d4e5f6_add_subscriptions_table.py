"""add subscriptions table

Revision ID: a1b2c3d4e5f6
Revises: 3bef0691f0fa
Create Date: 2026-03-01 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str]] = '3bef0691f0fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create subscriptions table."""
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), index=True, nullable=False),
        sa.Column('user_id', sa.String(36), index=True, nullable=False),
        sa.Column('stripe_customer_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), unique=True, nullable=True),
        sa.Column('plan', sa.String(32), nullable=False, server_default='free'),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Drop subscriptions table."""
    op.drop_table('subscriptions')
