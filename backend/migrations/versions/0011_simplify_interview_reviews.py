"""Keep interview reviews focused on structured question records."""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    # These free-text fields are intentionally removed. Their existing values
    # cannot be reconstructed by a downgrade, so back up before upgrading.
    with op.batch_alter_table("career_reviews") as batch_op:
        batch_op.drop_column("summary")
        batch_op.drop_column("strengths")
        batch_op.drop_column("improvements")
        batch_op.drop_column("next_action")


def downgrade():
    with op.batch_alter_table("career_reviews") as batch_op:
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=False,
                                      server_default=sa.text("''")))
        batch_op.add_column(sa.Column("strengths", sa.String(2000), nullable=False,
                                      server_default=sa.text("''")))
        batch_op.add_column(sa.Column("improvements", sa.String(2000), nullable=False,
                                      server_default=sa.text("''")))
        batch_op.add_column(sa.Column("next_action", sa.String(2000), nullable=False,
                                      server_default=sa.text("''")))

