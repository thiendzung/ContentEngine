"""Add eval ContentRun mode for CE03 replay/regression."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0010"
down_revision: str | None = "20260906_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_content_run_mode", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_mode",
        "content_runs",
        "run_mode in ('create','update','refresh','localize','eval')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    eval_count = bind.execute(
        sa.text("select count(*) from content_runs where run_mode = 'eval'")
    ).scalar_one()
    if eval_count:
        raise RuntimeError(
            "cannot downgrade 20260906_0010 while eval ContentRun rows exist"
        )

    op.drop_constraint("ck_content_run_mode", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_mode",
        "content_runs",
        "run_mode in ('create','update','refresh','localize')",
    )
