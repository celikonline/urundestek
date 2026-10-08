"""Rich messages and private ticket attachments.

Revision ID: 5f1497ec820a
Revises: c249eb715d01
"""
from alembic import op
import sqlalchemy as sa

revision = "5f1497ec820a"
down_revision = "c249eb715d01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("body_html", sa.Text(), nullable=True))
    op.create_table("attachments", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("tenant_id", sa.String(36), nullable=False),
                    sa.Column("ticket_id", sa.String(36), nullable=False),
                    sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=False),
                    sa.Column("filename", sa.String(200), nullable=False),
                    sa.Column("content_type", sa.String(100), nullable=False),
                    sa.Column("size", sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]))
    op.create_index("ix_attachment_message", "attachments", ["message_id"])


def downgrade():
    op.drop_table("attachments")
    op.drop_column("messages", "body_html")
