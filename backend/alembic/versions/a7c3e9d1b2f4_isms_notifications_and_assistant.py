"""ISMS controls, e-mail notifications and the support assistant.

Revision ID: a7c3e9d1b2f4
Revises: 5f1497ec820a
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c3e9d1b2f4"
down_revision = "5f1497ec820a"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN works on SQLite and PostgreSQL alike; batch mode would recreate tables and trip foreign keys.
    op.add_column("users", sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("ai_mode", sa.String(10), nullable=False, server_default="inherit"))
    op.create_table("outbound_emails", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("tenant_id", sa.String(36), nullable=False),
                    sa.Column("ticket_id", sa.String(36), nullable=False),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("kind", sa.String(20), nullable=False),
                    sa.Column("subject", sa.String(200), nullable=False),
                    sa.Column("body", sa.Text(), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
                    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("last_error", sa.String(300), nullable=True),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
                    sa.ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]))
    op.create_index("ix_outbound_email_status_created", "outbound_emails", ["status", "created_at"])
    op.create_table("ai_jobs", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("tenant_id", sa.String(36), nullable=False),
                    sa.Column("ticket_id", sa.String(36), nullable=False),
                    sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=False),
                    sa.Column("trigger", sa.String(20), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
                    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("result", sa.String(300), nullable=True),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
                    sa.ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]))
    op.create_index("ix_ai_job_status_created", "ai_jobs", ["status", "created_at"])
    op.create_table("audit_logs", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
                    sa.Column("actor_name", sa.String(200), nullable=False, server_default=""),
                    sa.Column("actor_role", sa.String(30), nullable=False, server_default=""),
                    sa.Column("tenant_id", sa.String(36), nullable=True),
                    sa.Column("action", sa.String(60), nullable=False),
                    sa.Column("target_type", sa.String(30), nullable=False, server_default=""),
                    sa.Column("target_id", sa.String(120), nullable=False, server_default=""),
                    sa.Column("detail", sa.String(300), nullable=False, server_default=""),
                    sa.Column("outcome", sa.String(20), nullable=False, server_default="success"),
                    sa.Column("ip", sa.String(64), nullable=False, server_default=""),
                    sa.Column("user_agent", sa.String(200), nullable=False, server_default=""),
                    sa.Column("correlation_id", sa.String(36), nullable=False, server_default=""),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_action_created", "audit_logs", ["action", "created_at"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("ai_jobs")
    op.drop_table("outbound_emails")
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("ai_mode")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("last_seen_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
        batch.drop_column("locked_until")
        batch.drop_column("failed_logins")
        batch.drop_column("email_notifications")
