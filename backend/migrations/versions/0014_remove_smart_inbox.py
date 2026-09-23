"""Remove the smart inbox, 163 mail integration, and their persisted data."""

from alembic import context, op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    run_ids = sa.select(sa.column("id")).select_from(sa.table("agent_runs")).where(
        sa.column("skill").in_(("job_ingestion", "mail_analysis"))
    )
    connection.execute(
        sa.delete(sa.table("agent_events", sa.column("run_id"))).where(
            sa.column("run_id").in_(run_ids)
        )
    )
    connection.execute(
        sa.delete(sa.table("agent_runs", sa.column("skill"))).where(
            sa.column("skill").in_(("job_ingestion", "mail_analysis"))
        )
    )
    for table in (
        "external_notifications",
        "external_items",
        "external_jobs",
        "external_oauth_attempts",
        "external_connections",
    ):
        op.drop_table(table)


def downgrade():
    allowed = context.get_context().config.attributes.get("allow_external_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_external_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError(
            "降级只能恢复空的收件箱表，无法恢复已删除数据；"
            "请备份并显式允许 allow_external_downgrade"
        )
    op.create_table(
        "external_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("scope", sa.String(256), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("account_email", sa.String(254), nullable=False, server_default=""),
        sa.Column("sync_cursor", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "uq_external_connection_user_kind",
        "external_connections",
        ["user_id", "kind"],
        unique=True,
    )
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
    op.create_index("ix_external_jobs_user_id", "external_jobs", ["user_id"])
    op.create_index("ix_external_jobs_connection_id", "external_jobs", ["connection_id"])
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
    op.create_index("ix_external_items_user_id", "external_items", ["user_id"])
    op.create_index("ix_external_items_connection_id", "external_items", ["connection_id"])
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
