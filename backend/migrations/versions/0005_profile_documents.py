"""Versioned career documents, owned retrieval chunks, and user-managed memory."""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "career_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_career_documents_user_id", "career_documents", ["user_id"])
    op.create_index("uq_career_documents_id_owner", "career_documents", ["id", "user_id"], unique=True)

    op.create_table(
        "career_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text().with_variant(LONGTEXT, "mysql"), nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"], ["career_documents.id", "career_documents.user_id"],
            name="fk_career_document_versions_owner", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_career_document_versions_document_id", "career_document_versions", ["document_id"])
    op.create_index("ix_career_document_versions_user_id", "career_document_versions", ["user_id"])
    op.create_index("uq_career_document_versions_owner_id", "career_document_versions", ["id", "user_id"], unique=True)
    op.create_index("uq_career_document_versions_number", "career_document_versions", ["document_id", "version"], unique=True)

    op.create_table(
        "career_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id", "user_id"],
            ["career_document_versions.id", "career_document_versions.user_id"],
            name="fk_career_document_chunks_owner", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_career_document_chunks_version_id", "career_document_chunks", ["version_id"])
    op.create_index("ix_career_document_chunks_user_id", "career_document_chunks", ["user_id"])
    op.create_index("uq_career_document_chunks_ordinal", "career_document_chunks", ["version_id", "ordinal"], unique=True)

    op.create_table(
        "career_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_version_id", sa.Integer(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_version_id", "user_id"],
            ["career_document_versions.id", "career_document_versions.user_id"],
            name="fk_career_memories_source_owner", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_career_memories_user_id", "career_memories", ["user_id"])
    op.create_index("ix_career_memories_source_version_id", "career_memories", ["source_version_id"])


def downgrade():
    config = context.get_context().config
    allowed = config.attributes.get("allow_profile_downgrade") or (
        context.get_x_argument(as_dictionary=True).get("allow_profile_downgrade") == "true"
    )
    if not allowed:
        raise RuntimeError("降级会删除画像、文档与索引，请备份并显式允许 allow_profile_downgrade")
    op.drop_table("career_memories")
    op.drop_table("career_document_chunks")
    op.drop_table("career_document_versions")
    op.drop_table("career_documents")
