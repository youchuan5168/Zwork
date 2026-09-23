"""User-owned action tasks and interview/weekly review records."""

from alembic import context, op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "career_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("details", sa.String(2000), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("source_label", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("user_id", "due_date", "done", "application_id"):
        op.create_index(f"ix_career_tasks_{column}", "career_tasks", [column])
    op.create_table(
        "career_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("source_label", sa.String(256), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", sa.String(2000), nullable=False),
        sa.Column("improvements", sa.String(2000), nullable=False),
        sa.Column("next_action", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("user_id", "application_id", "schedule_id", "occurred_on"):
        op.create_index(f"ix_career_reviews_{column}", "career_reviews", [column])


def downgrade():
    config = context.get_context().config
    allowed = config.attributes.get("allow_career_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_career_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除待办与复盘，请备份并显式允许 allow_career_downgrade")
    op.drop_table("career_reviews")
    op.drop_table("career_tasks")
