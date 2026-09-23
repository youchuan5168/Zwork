"""Add 163 IMAP account identity and incremental cursor."""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "external_connections",
        sa.Column("account_email", sa.String(254), nullable=False, server_default=""),
    )
    op.add_column(
        "external_connections",
        sa.Column("sync_cursor", sa.String(128), nullable=False, server_default=""),
    )
    # Prior releases used these rows for Google mail/calendar. Keep them recoverable but
    # make them inactive so only a newly verified 163 connection is exposed or synced.
    op.execute(sa.text("UPDATE external_connections SET status = 'legacy'"))


def downgrade():
    op.drop_column("external_connections", "sync_cursor")
    op.drop_column("external_connections", "account_email")
