"""Add GitHub users and authenticated worklog ownership."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("github_user_id", sa.BigInteger(), nullable=True),
        sa.Column("github_login", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_user_id"),
    )
    op.create_index("ix_users_github_login", "users", ["github_login"])
    op.add_column("worklogs", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.execute(
        f"""
        INSERT INTO users (id, github_login, display_name)
        SELECT '{LEGACY_USER_ID}', 'legacy-development-owner', 'Legacy development owner'
        WHERE EXISTS (SELECT 1 FROM worklogs)
        """
    )
    op.execute(f"UPDATE worklogs SET user_id = '{LEGACY_USER_ID}' WHERE user_id IS NULL")
    op.alter_column("worklogs", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_worklogs_user_id_users", "worklogs", "users", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.drop_index("ix_worklogs_chronology", table_name="worklogs")
    op.create_index(
        "ix_worklogs_owner_chronology",
        "worklogs",
        ["user_id", "date", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_worklogs_owner_chronology", table_name="worklogs")
    op.create_index("ix_worklogs_chronology", "worklogs", ["date", "created_at", "id"])
    op.drop_constraint("fk_worklogs_user_id_users", "worklogs", type_="foreignkey")
    op.drop_column("worklogs", "user_id")
    op.drop_index("ix_users_github_login", table_name="users")
    op.drop_table("users")
