"""Structured per-question records attached to career reviews."""

from alembic import context, op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.String(2000), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("user_id", "review_id", "application_id"):
        op.create_index(f"ix_interview_questions_{column}", "interview_questions", [column])


def downgrade():
    config = context.get_context().config
    allowed = config.attributes.get("allow_career_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_career_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除面试题目记录，请备份并显式允许 allow_career_downgrade")
    op.drop_table("interview_questions")
