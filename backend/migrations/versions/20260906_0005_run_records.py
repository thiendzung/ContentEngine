"""CE02 PR-D run records and context manifests."""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0005"
down_revision: str | None = "20260906_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "content_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), sa.ForeignKey("content_cases.id"), nullable=False),
        sa.Column("locale_variant_id", sa.Uuid(), sa.ForeignKey("locale_variants.id"), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), sa.ForeignKey("content_items.id")),
        sa.Column("run_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(64)),
        sa.Column("settings_snapshot_id", sa.Uuid(), sa.ForeignKey("settings_snapshots.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("failure_message", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("run_mode in ('create','update','refresh','localize')", name="ck_content_run_mode"),
        sa.CheckConstraint("status in ('pending','running','paused','completed','failed','cancelled')", name="ck_content_run_status"),
    )
    op.create_table(
        "step_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_key", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_artifact_refs_json", sa.JSON(), nullable=False),
        sa.Column("output_artifact_refs_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_json", sa.JSON()),
        *_timestamps(),
        sa.CheckConstraint("attempt > 0", name="ck_step_run_attempt_positive"),
        sa.CheckConstraint("status in ('pending','running','completed','failed','skipped')", name="ck_step_run_status"),
        sa.UniqueConstraint("run_id", "step_key", "attempt", name="uq_step_run_attempt"),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), sa.ForeignKey("step_runs.id")),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(32)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON()),
        sa.Column("external_ref", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version > 0", name="ck_artifact_version_positive"),
        sa.CheckConstraint("content_json is not null or external_ref is not null", name="ck_artifact_has_content"),
        sa.UniqueConstraint("run_id", "artifact_type", "version", name="uq_artifact_run_type_version"),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("step_key", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("comment", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("decision in ('approved','rejected','changes_requested')", name="ck_approval_decision"),
    )
    op.create_table(
        "context_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), sa.ForeignKey("step_runs.id")),
        sa.Column("settings_snapshot_id", sa.Uuid(), sa.ForeignKey("settings_snapshots.id"), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("recipe_version", sa.String(100), nullable=False),
        sa.Column("evidence_set_id", sa.Uuid(), sa.ForeignKey("evidence_sets.id")),
        sa.Column("knowledge_chunk_refs_json", sa.JSON(), nullable=False),
        sa.Column("golden_example_refs_json", sa.JSON(), nullable=False),
        sa.Column("tool_result_refs_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), sa.ForeignKey("step_runs.id")),
        sa.Column("context_manifest_id", sa.Uuid(), sa.ForeignKey("context_manifests.id")),
        sa.Column("task_key", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cost", sa.Numeric(12, 6)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("finish_reason", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_class", sa.String(64)),
        sa.Column("result_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id")),
        *_timestamps(),
        sa.CheckConstraint("status in ('pending','running','completed','failed')", name="ck_model_call_status"),
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), sa.ForeignKey("step_runs.id")),
        sa.Column("tool_key", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_ref", sa.Text()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_class", sa.String(64)),
        *_timestamps(),
        sa.CheckConstraint("status in ('pending','running','completed','failed')", name="ck_tool_call_status"),
    )
    op.create_table(
        "quality_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("evaluator_key", sa.String(100), nullable=False),
        sa.Column("evaluator_version", sa.String(100), nullable=False),
        sa.Column("evaluator_type", sa.String(64), nullable=False),
        sa.Column("result", sa.String(64), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("severity", sa.String(32)),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("result in ('pass','fail','warn')", name="ck_quality_evaluation_result"),
        sa.CheckConstraint("evaluator_type in ('deterministic','model','human')", name="ck_quality_evaluation_type"),
    )
    op.execute(sa.text("CREATE FUNCTION prevent_context_manifest_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'context_manifest_is_immutable'; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER context_manifests_immutable BEFORE UPDATE OR DELETE ON context_manifests FOR EACH ROW EXECUTE FUNCTION prevent_context_manifest_mutation()"))
    op.execute(sa.text("CREATE FUNCTION prevent_artifact_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'artifact_is_immutable'; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER artifacts_immutable BEFORE UPDATE OR DELETE ON artifacts FOR EACH ROW EXECUTE FUNCTION prevent_artifact_mutation()"))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS context_manifests_immutable ON context_manifests")
    op.execute("DROP FUNCTION IF EXISTS prevent_context_manifest_mutation")
    op.execute("DROP TRIGGER IF EXISTS artifacts_immutable ON artifacts")
    op.execute("DROP FUNCTION IF EXISTS prevent_artifact_mutation")
    op.drop_table("quality_evaluations")
    op.drop_table("tool_calls")
    op.drop_table("model_calls")
    op.drop_table("context_manifests")
    op.drop_table("approvals")
    op.drop_table("artifacts")
    op.drop_table("step_runs")
    op.drop_table("content_runs")
