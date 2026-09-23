"""Per-user large model API endpoint settings."""

from alembic import context, op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_llm_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("api_url", sa.String(512), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uq_user_llm_configs_user", "user_llm_configs", ["user_id"], unique=True)


def downgrade():
    allowed = context.get_context().config.attributes.get("allow_llm_settings_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_llm_settings_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除用户的大模型 API 配置，请备份并显式允许 allow_llm_settings_downgrade")
    op.drop_table("user_llm_configs")
