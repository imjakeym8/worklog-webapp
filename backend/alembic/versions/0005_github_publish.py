"""Add minimal GitHub repository and Markdown publication provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("github_repository_id", sa.BigInteger(), nullable=False),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("full_name", sa.String(201), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column("html_url", sa.String(500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "github_repository_id", name="uq_github_repo_user"),
    )
    op.create_index("ix_github_repositories_user_id", "github_repositories", ["user_id"])
    op.create_table(
        "markdown_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("worklog_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("last_published_file_sha", sa.String(100), nullable=False),
        sa.Column("last_published_commit_sha", sa.String(100), nullable=False),
        sa.Column("last_published_content_hash", sa.String(64), nullable=False),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklogs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["github_repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worklog_id", "repository_id", "path", name="uq_markdown_publication"),
    )


def downgrade() -> None:
    op.drop_table("markdown_publications")
    op.drop_index("ix_github_repositories_user_id", table_name="github_repositories")
    op.drop_table("github_repositories")
