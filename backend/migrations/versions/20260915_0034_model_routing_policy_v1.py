"""Add immutable audit records for model routing policy v1."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0034"
down_revision: str | None = "20260915_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_route_decision_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_model_route_decision() RETURNS trigger AS $$
            DECLARE
                call_run uuid;
                call_step uuid;
                call_manifest uuid;
                call_task text;
                call_provider text;
                call_model text;
                manifest_settings uuid;
                settings_hash text;
                expected_route_key text;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'model_route_decision_is_immutable';
                END IF;

                SELECT
                    run_id,
                    step_run_id,
                    context_manifest_id,
                    task_key,
                    provider,
                    model
                INTO
                    call_run,
                    call_step,
                    call_manifest,
                    call_task,
                    call_provider,
                    call_model
                FROM model_calls
                WHERE id = NEW.model_call_id;

                IF call_run IS NULL THEN
                    RAISE EXCEPTION 'model_route_decision_call_not_found';
                END IF;
                IF call_run IS DISTINCT FROM NEW.run_id
                   OR call_step IS DISTINCT FROM NEW.step_run_id
                   OR call_task IS DISTINCT FROM NEW.task_key THEN
                    RAISE EXCEPTION 'model_route_decision_call_binding_mismatch';
                END IF;
                IF call_manifest IS NULL THEN
                    RAISE EXCEPTION 'model_route_decision_manifest_required';
                END IF;

                SELECT settings_snapshot_id INTO manifest_settings
                FROM context_manifests
                WHERE id = call_manifest;
                IF manifest_settings IS DISTINCT FROM NEW.settings_snapshot_id THEN
                    RAISE EXCEPTION 'model_route_decision_settings_binding_mismatch';
                END IF;

                SELECT content_hash INTO settings_hash
                FROM settings_snapshots
                WHERE id = NEW.settings_snapshot_id;
                IF settings_hash IS NULL THEN
                    RAISE EXCEPTION 'model_route_decision_settings_not_found';
                END IF;

                expected_route_key := 'policy:' || NEW.policy_key || ':' || NEW.capability;
                IF NEW.route_snapshot_json->>'method' IS DISTINCT FROM
                       'model_routing_policy_v1'
                   OR NEW.route_snapshot_json->>'settings_snapshot_id' IS DISTINCT FROM
                       NEW.settings_snapshot_id::text
                   OR NEW.route_snapshot_json->>'settings_snapshot_hash' IS DISTINCT FROM
                       settings_hash
                   OR NEW.route_snapshot_json->>'task_key' IS DISTINCT FROM NEW.task_key
                   OR NEW.route_snapshot_json->>'route_key' IS DISTINCT FROM expected_route_key
                   OR NEW.route_snapshot_json->>'policy_key' IS DISTINCT FROM NEW.policy_key
                   OR (NEW.route_snapshot_json->>'policy_version')::integer IS DISTINCT FROM
                       NEW.policy_version
                   OR NEW.route_snapshot_json->>'capability' IS DISTINCT FROM NEW.capability
                   OR (NEW.route_snapshot_json->>'candidate_index')::integer IS DISTINCT FROM
                       NEW.candidate_index
                   OR NEW.route_snapshot_json->>'provider' IS DISTINCT FROM call_provider
                   OR NEW.route_snapshot_json->>'model' IS DISTINCT FROM call_model
                   OR NEW.route_snapshot_json->>'escalation_reason' IS DISTINCT FROM
                       NEW.escalation_reason
                   OR (NEW.route_snapshot_json->>'max_escalations')::integer IS DISTINCT FROM
                       NEW.max_escalations
                   OR (NEW.route_snapshot_json->>'max_model_calls_per_step')::integer
                       IS DISTINCT FROM NEW.max_model_calls_per_step THEN
                    RAISE EXCEPTION 'model_route_decision_snapshot_binding_mismatch';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER model_route_decisions_guard
            BEFORE INSERT OR UPDATE OR DELETE ON model_route_decisions
            FOR EACH ROW EXECUTE FUNCTION validate_model_route_decision()
            """
        )
    )


def _create_routed_model_call_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_routed_model_call_identity() RETURNS trigger AS $$
            DECLARE
                has_route_decision boolean;
            BEGIN
                SELECT EXISTS(
                    SELECT 1 FROM model_route_decisions WHERE model_call_id = OLD.id
                ) INTO has_route_decision;

                IF NOT has_route_decision THEN
                    IF TG_OP = 'DELETE' THEN
                        RETURN OLD;
                    END IF;
                    RETURN NEW;
                END IF;

                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'routed_model_call_delete_forbidden';
                END IF;

                IF OLD.run_id IS DISTINCT FROM NEW.run_id
                   OR OLD.step_run_id IS DISTINCT FROM NEW.step_run_id
                   OR OLD.context_manifest_id IS DISTINCT FROM NEW.context_manifest_id
                   OR OLD.task_key IS DISTINCT FROM NEW.task_key
                   OR OLD.provider IS DISTINCT FROM NEW.provider
                   OR OLD.model IS DISTINCT FROM NEW.model THEN
                    RAISE EXCEPTION 'routed_model_call_identity_is_immutable';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER routed_model_calls_guard
            BEFORE UPDATE OR DELETE ON model_calls
            FOR EACH ROW EXECUTE FUNCTION protect_routed_model_call_identity()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "model_route_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_call_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), nullable=False),
        sa.Column("settings_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("task_key", sa.String(length=100), nullable=False),
        sa.Column("policy_key", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("escalation_reason", sa.String(length=100), nullable=True),
        sa.Column("max_escalations", sa.Integer(), nullable=False),
        sa.Column("max_model_calls_per_step", sa.Integer(), nullable=False),
        sa.Column("route_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("route_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "policy_version > 0",
            name="ck_model_route_policy_version_positive",
        ),
        sa.CheckConstraint(
            "candidate_index >= 0",
            name="ck_model_route_candidate_index_nonnegative",
        ),
        sa.CheckConstraint(
            "max_escalations >= 0",
            name="ck_model_route_max_escalations_nonnegative",
        ),
        sa.CheckConstraint(
            "candidate_index <= max_escalations",
            name="ck_model_route_candidate_within_escalation_limit",
        ),
        sa.CheckConstraint(
            "max_model_calls_per_step > 0",
            name="ck_model_route_max_calls_positive",
        ),
        sa.CheckConstraint(
            "max_model_calls_per_step >= max_escalations + 1",
            name="ck_model_route_max_calls_cover_escalations",
        ),
        sa.CheckConstraint(
            "route_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_model_route_snapshot_hash",
        ),
        sa.CheckConstraint(
            "btrim(task_key) <> ''",
            name="ck_model_route_task_key_required",
        ),
        sa.CheckConstraint(
            "btrim(policy_key) <> ''",
            name="ck_model_route_policy_key_required",
        ),
        sa.CheckConstraint(
            "btrim(capability) <> ''",
            name="ck_model_route_capability_required",
        ),
        sa.ForeignKeyConstraint(
            ["model_call_id"],
            ["model_calls.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["content_runs.id"]),
        sa.ForeignKeyConstraint(["step_run_id"], ["step_runs.id"]),
        sa.ForeignKeyConstraint(
            ["settings_snapshot_id"],
            ["settings_snapshots.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_call_id",
            name="uq_model_route_decisions_call",
        ),
    )
    op.create_index(
        "ix_model_route_decisions_step_policy",
        "model_route_decisions",
        ["step_run_id", "policy_key", "capability"],
        unique=False,
    )
    op.create_index(
        "ix_model_route_decisions_settings",
        "model_route_decisions",
        ["settings_snapshot_id"],
        unique=False,
    )
    _create_route_decision_guard()
    _create_routed_model_call_guard()


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS routed_model_calls_guard ON model_calls"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS protect_routed_model_call_identity()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS model_route_decisions_guard "
            "ON model_route_decisions"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_model_route_decision()"))
    op.drop_index(
        "ix_model_route_decisions_settings",
        table_name="model_route_decisions",
    )
    op.drop_index(
        "ix_model_route_decisions_step_policy",
        table_name="model_route_decisions",
    )
    op.drop_table("model_route_decisions")
