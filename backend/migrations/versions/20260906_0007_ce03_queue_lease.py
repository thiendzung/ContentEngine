"""CE03 durable queue and worker lease core."""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0007"
down_revision: str | None = "20260906_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE content_runs SET status = 'waiting_approval' WHERE status = 'paused'")
    op.drop_constraint("ck_content_run_status", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_status",
        "content_runs",
        "status in ('pending','running','waiting_approval','completed','failed','cancelled')",
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION validate_content_run_status_transition() RETURNS trigger AS $$ BEGIN IF NEW.status <> OLD.status AND NOT ((OLD.status = 'pending' AND NEW.status IN ('running', 'cancelled')) OR (OLD.status = 'running' AND NEW.status IN ('waiting_approval', 'completed', 'failed', 'cancelled')) OR (OLD.status = 'waiting_approval' AND NEW.status IN ('running', 'cancelled'))) THEN RAISE EXCEPTION 'invalid_content_run_status_transition'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER content_run_status_transition_guard BEFORE UPDATE ON content_runs FOR EACH ROW EXECUTE FUNCTION validate_content_run_status_transition()"
        )
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION validate_step_run_status_transition() RETURNS trigger AS $$ BEGIN IF NEW.status <> OLD.status AND NOT ((OLD.status = 'pending' AND NEW.status = 'running') OR (OLD.status = 'running' AND NEW.status IN ('completed', 'failed'))) THEN RAISE EXCEPTION 'invalid_step_run_status_transition'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER step_run_status_transition_guard BEFORE UPDATE ON step_runs FOR EACH ROW EXECUTE FUNCTION validate_step_run_status_transition()"
        )
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), sa.ForeignKey("step_runs.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt > 0", name="ck_job_attempt_positive"),
        sa.CheckConstraint(
            "status in ('queued','leased','completed','failed','cancelled')", name="ck_job_status"
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_job_dedupe_key"),
    )
    op.create_index("ix_jobs_claimable", "jobs", ["status", "available_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_claimable", table_name="jobs")
    op.drop_table("jobs")
    op.execute("DROP TRIGGER IF EXISTS step_run_status_transition_guard ON step_runs")
    op.execute("DROP FUNCTION IF EXISTS validate_step_run_status_transition")
    op.execute("DROP TRIGGER IF EXISTS content_run_status_transition_guard ON content_runs")
    op.execute("DROP FUNCTION IF EXISTS validate_content_run_status_transition")
    op.execute("UPDATE content_runs SET status = 'paused' WHERE status = 'waiting_approval'")
    op.drop_constraint("ck_content_run_status", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_status",
        "content_runs",
        "status in ('pending','running','paused','completed','failed','cancelled')",
    )
