"""持久化 Agent 运行与生命周期事件；不修改既有业务数据。"""

from alembic import op, context
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("active_slot", sa.Integer(), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("tool_version", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("pricing", sa.JSON(), nullable=False),
        sa.Column("pending", sa.JSON(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("execution_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("uq_agent_runs_id_owner", "agent_runs", ["id", "user_id"], unique=True)
    op.create_index("uq_agent_runs_request", "agent_runs", ["user_id", "request_key"], unique=True)
    op.create_index("uq_agent_runs_active", "agent_runs", ["user_id", "active_slot"], unique=True)
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "user_id"], ["agent_runs.id", "agent_runs.user_id"],
            name="fk_agent_events_run_owner", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_agent_events_user_id", "agent_events", ["user_id"])
    op.create_index("uq_agent_events_sequence", "agent_events", ["run_id", "sequence"], unique=True)
    op.create_index("ix_agent_events_run_owner", "agent_events", ["run_id", "user_id"])


def downgrade():
    config = context.get_context().config
    allowed = config.attributes.get("allow_agent_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_agent_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除 Agent 运行/审批审计，请备份并显式允许 allow_agent_downgrade")
    op.drop_table("agent_events")
    op.drop_table("agent_runs")
