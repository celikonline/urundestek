"""Response target, customer rating.

Revision ID: c81d2f6e4a90
Revises: a7c3e9d1b2f4
"""
from alembic import op
import sqlalchemy as sa

revision = "c81d2f6e4a90"
down_revision = "a7c3e9d1b2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("rating", sa.Integer(), nullable=True))
    op.add_column("tickets", sa.Column("rating_comment", sa.String(500), nullable=True))
    op.add_column("tickets", sa.Column("rated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("tickets") as batch:
        batch.drop_column("rated_at")
        batch.drop_column("rating_comment")
        batch.drop_column("rating")
        batch.drop_column("first_response_at")
