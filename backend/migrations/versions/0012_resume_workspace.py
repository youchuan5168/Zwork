"""Default resume selection for the unified resume workspace."""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "career_documents",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("career_documents", "is_default")
