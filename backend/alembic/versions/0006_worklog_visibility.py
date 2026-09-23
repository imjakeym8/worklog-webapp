"""Add safe public/private visibility to worklogs."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing journal records remain private until their owner explicitly publishes them.
    op.add_column(
        "worklogs",
        sa.Column("visibility", sa.String(length=7), server_default="private", nullable=False),
    )
    op.create_check_constraint(
        "ck_worklogs_visibility", "worklogs", "visibility IN ('public', 'private')"
    )
    op.create_index(
        "ix_worklogs_public_chronology",
        "worklogs",
        ["visibility", "date", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_worklogs_public_chronology", table_name="worklogs")
    op.drop_constraint("ck_worklogs_visibility", "worklogs", type_="check")
    op.drop_column("worklogs", "visibility")
