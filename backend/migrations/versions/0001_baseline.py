"""冻结现有五张表的基线；现有数据库核对结构后 stamp 0001。

本次重构不自动执行迁移，不修改用户已有数据。
"""

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("industry", sa.String(64), nullable=False),
        sa.Column("website", sa.String(256), nullable=False),
        sa.Column("notes", AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=True)
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("company_name", sa.String(128), nullable=False),
        sa.Column("position", sa.String(128), nullable=False),
        sa.Column("channel", sa.String(512), nullable=False),
        sa.Column("apply_date", sa.Date, nullable=False),
        sa.Column("current_stage", sa.String(32), nullable=False),
        sa.Column("notes", AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_applications_company_name", "applications", ["company_name"], unique=False)
    op.create_index("ix_applications_position", "applications", ["position"], unique=False)
    op.create_index("ix_applications_apply_date", "applications", ["apply_date"], unique=False)
    op.create_index(
        "ix_applications_current_stage", "applications", ["current_stage"], unique=False
    )
    op.create_table(
        "application_stages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("changed_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_application_stages_application_id",
        "application_stages",
        ["application_id"],
        unique=False,
    )
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("sched_date", sa.Date, nullable=False),
        sa.Column("sched_time", sa.String(16), nullable=False),
        sa.Column("link", sa.String(512), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("done", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_schedules_application_id", "schedules", ["application_id"], unique=False)
    op.create_index("ix_schedules_sched_date", "schedules", ["sched_date"], unique=False)
    op.create_index("ix_schedules_done", "schedules", ["done"], unique=False)


def downgrade():
    op.drop_table("schedules")
    op.drop_table("application_stages")
    op.drop_table("applications")
    op.drop_table("companies")
    op.drop_table("users")
