"""initial schema

Revision ID: 3bef0691f0fa
Revises:
Create Date: 2026-03-01 20:13:03.396146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3bef0691f0fa'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, index=True, nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'token_caches',
        sa.Column('user_id', sa.String(36), primary_key=True),
        sa.Column('cache_blob', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), index=True, nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('chat_sessions.id'), index=True, nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'chat_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('chat_sessions.id'), index=True, nullable=True),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('chunk_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'pending_task_sets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('chat_sessions.id'), index=True, nullable=False),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('chat_messages.id'), nullable=False),
        sa.Column('tasks_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), default='pending', nullable=False),
        sa.Column('plan_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('pending_task_sets')
    op.drop_table('chat_documents')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('token_caches')
    op.drop_table('users')
