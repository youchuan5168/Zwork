"""收件箱技能列；不修改既有运行数据与业务表。"""

from alembic import op, context
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_runs",
        sa.Column("skill", sa.String(32), nullable=False, server_default="assistant"),
    )


def downgrade():
    config = context.get_context().config
    allowed = config.attributes.get("allow_agent_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_agent_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会丢失运行技能归属，请备份并显式允许 allow_agent_downgrade")
    op.drop_column("agent_runs", "skill")
