"""Add token_count, is_public, view_count to query_history

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "query_history",
        sa.Column("token_count", sa.Integer(), nullable=True, default=0),
    )
    op.add_column(
        "query_history",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "query_history",
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("query_history", "view_count")
    op.drop_column("query_history", "is_public")
    op.drop_column("query_history", "token_count")
