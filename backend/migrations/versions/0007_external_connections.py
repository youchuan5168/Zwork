"""Read-only external connections, sync jobs and notifications."""

from alembic import context, op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "external_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("scope", sa.String(256), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_external_connection_user_kind", "external_connections", ["user_id", "kind"], unique=True)
    op.create_index("ix_external_connections_user_id", "external_connections", ["user_id"])
    op.create_table(
        "external_oauth_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_external_oauth_attempts_user_id", "external_oauth_attempts", ["user_id"])
    op.create_table(
        "external_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("external_connections.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_external_job_request", "external_jobs", ["user_id", "request_key"], unique=True)
    for column in ("user_id", "connection_id"):
        op.create_index(f"ix_external_jobs_{column}", "external_jobs", [column])
    op.create_table(
        "external_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("external_connections.id"), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("snippet", sa.String(2000), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_external_item_source", "external_items", ["connection_id", "source_id"], unique=True)
    for column in ("user_id", "connection_id"):
        op.create_index(f"ix_external_items_{column}", "external_items", [column])
    op.create_table(
        "external_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("external_items.id"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_external_notification_item", "external_notifications", ["item_id"], unique=True)
    op.create_index("ix_external_notifications_user_id", "external_notifications", ["user_id"])


def downgrade():
    allowed = context.get_context().config.attributes.get("allow_external_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_external_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除连接、同步记录和通知，请备份并显式允许 allow_external_downgrade")
    for table in ("external_notifications", "external_items", "external_jobs",
                  "external_oauth_attempts", "external_connections"):
        op.drop_table(table)
