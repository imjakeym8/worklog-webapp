"""Create worklogs, reusable tracks, and automatic update timestamps."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_tracks_name"),
    )
    op.create_table(
        "worklogs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(8, 2), nullable=False),
        sa.Column("shipped", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("activity_breakdown", sa.Text(), nullable=False),
        sa.Column("detailed_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("quick_summary", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "blockers",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "next_steps",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("hours > 0", name="ck_worklogs_hours_positive"),
        sa.CheckConstraint("length(btrim(activity_breakdown)) > 0", name="ck_worklogs_activity"),
        sa.CheckConstraint("cardinality(blockers) <= 50", name="ck_worklogs_blockers_count"),
        sa.CheckConstraint("cardinality(next_steps) <= 50", name="ck_worklogs_next_count"),
    )
    op.create_index("ix_worklogs_chronology", "worklogs", ["date", "created_at", "id"])
    op.create_table(
        "worklog_tracks",
        sa.Column(
            "worklog_id",
            sa.Uuid(),
            sa.ForeignKey("worklogs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "track_id", sa.Uuid(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_index("ix_worklog_tracks_track_id", "worklog_tracks", ["track_id"])
    op.execute("""
        CREATE FUNCTION touch_worklog_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER worklogs_updated_at BEFORE UPDATE ON worklogs
        FOR EACH ROW EXECUTE FUNCTION touch_worklog_updated_at()
    """)


def downgrade() -> None:
    op.drop_table("worklog_tracks")
    op.drop_table("worklogs")
    op.execute("DROP FUNCTION touch_worklog_updated_at()")
    op.drop_table("tracks")
