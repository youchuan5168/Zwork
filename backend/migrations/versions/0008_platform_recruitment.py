"""Recruitment preferences and reviewed job queue."""

from alembic import context, op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recruitment_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("keyword", sa.String(128), nullable=False),
        sa.Column("city", sa.String(64), nullable=False),
        sa.Column("resume_document_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_recruitment_preferences_user", "recruitment_preferences", ["user_id"], unique=True)
    op.create_table(
        "recruitment_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("url_key", sa.String(64), nullable=False),
        sa.Column("company_name", sa.String(128), nullable=False),
        sa.Column("position", sa.String(128), nullable=False),
        sa.Column("city", sa.String(64), nullable=False),
        sa.Column("salary", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result_kind", sa.String(24), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recruitment_jobs_user_id", "recruitment_jobs", ["user_id"])
    op.create_index("uq_recruitment_jobs_owner_url", "recruitment_jobs", ["user_id", "url_key"], unique=True)
    op.create_index("ix_recruitment_jobs_owner_status", "recruitment_jobs", ["user_id", "status"])


def downgrade():
    allowed = context.get_context().config.attributes.get("allow_recruitment_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_recruitment_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除平台岗位与筛选条件，请备份并显式允许 allow_recruitment_downgrade")
    op.drop_table("recruitment_jobs")
    op.drop_table("recruitment_preferences")
