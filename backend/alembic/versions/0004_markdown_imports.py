"""Track Markdown import provenance for duplicate-safe portability."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markdown_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("worklog_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklogs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source_key", name="uq_markdown_import_source"),
    )
    op.create_index("ix_markdown_imports_user_id", "markdown_imports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_markdown_imports_user_id", table_name="markdown_imports")
    op.drop_table("markdown_imports")
