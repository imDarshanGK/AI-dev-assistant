"""Add user profile fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "updated_at")
    op.drop_column("users", "bio")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "full_name")
