"""Add PM-01 publication and measurement identity.

Revision ID: 20260922_0039
Revises: 20260922_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0039"
down_revision: str | None = "20260922_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_content_run_mode", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_mode",
        "content_runs",
        "run_mode in ('create','update','refresh','localize','eval','publish')",
    )

    op.create_table(
        "published_contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("current_content_version_id", sa.Uuid(), nullable=False),
        sa.Column("external_revision_id", sa.String(length=255), nullable=True),
        sa.Column("external_status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target in ('wordpress')",
            name="ck_published_content_target",
        ),
        sa.CheckConstraint(
            "external_status in ('draft','publish','future','private')",
            name="ck_published_content_external_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(
            ["current_content_version_id"],
            ["content_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "content_item_id",
            "target",
            name="uq_published_content_item_target",
        ),
        sa.UniqueConstraint(
            "project_id",
            "target",
            "external_id",
            name="uq_published_content_external_id",
        ),
    )
    op.create_index(
        "ix_published_contents_project_url",
        "published_contents",
        ["project_id", "canonical_url"],
        unique=False,
    )

    op.create_table(
        "publish_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("published_content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("publish_package_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("publish_approval_id", sa.Uuid(), nullable=False),
        sa.Column("outbox_intent_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("external_revision_id", sa.String(length=255), nullable=True),
        sa.Column("external_status", sa.String(length=32), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action in ('draft','publish','update_draft','update_publish')",
            name="ck_publish_event_action",
        ),
        sa.CheckConstraint(
            "external_status in ('draft','publish','future','private')",
            name="ck_publish_event_external_status",
        ),
        sa.ForeignKeyConstraint(
            ["published_content_id"],
            ["published_contents.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_experiment_id"],
            ["content_experiments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["publish_package_artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(["publish_approval_id"], ["approvals.id"]),
        sa.ForeignKeyConstraint(["outbox_intent_id"], ["outbox_intents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_publish_event_idempotency_key",
        ),
        sa.UniqueConstraint(
            "outbox_intent_id",
            name="uq_publish_event_outbox_intent",
        ),
    )
    op.create_index(
        "ix_publish_events_content_version",
        "publish_events",
        ["content_version_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_publish_events_experiment",
        "publish_events",
        ["content_experiment_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("published_content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("raw_metrics_json", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider in ('search_console','analytics','motgu_conversion','rank_math')",
            name="ck_performance_snapshot_provider",
        ),
        sa.CheckConstraint(
            "window_end >= window_start",
            name="ck_performance_snapshot_window",
        ),
        sa.ForeignKeyConstraint(
            ["published_content_id"],
            ["published_contents.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "published_content_id",
            "provider",
            "window_start",
            "window_end",
            "payload_fingerprint",
            name="uq_performance_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_performance_snapshots_published_window",
        "performance_snapshots",
        ["published_content_id", "window_end"],
        unique=False,
    )

    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("published_content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("metric_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("dimensions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "metric_name in ("
            "'impressions','clicks','sessions','engaged_sessions',"
            "'artwork_transition','visit_transition','workshop_transition','inquiry'"
            ")",
            name="ck_performance_metric_name",
        ),
        sa.CheckConstraint(
            "metric_value >= 0",
            name="ck_performance_metric_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["performance_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["published_content_id"],
            ["published_contents.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "metric_date",
            "metric_name",
            name="uq_performance_metric_snapshot_date_name",
        ),
    )
    op.create_index(
        "ix_performance_metrics_content_name_date",
        "performance_metrics",
        ["published_content_id", "metric_name", "metric_date"],
        unique=False,
    )

    op.create_table(
        "content_performance_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("published_content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("observation_type", sa.String(length=64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("metric_refs_json", sa.JSON(), nullable=False),
        sa.Column("data_status", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "data_status in ("
            "'INSUFFICIENT_DATA','EARLY_SIGNAL','REPEATED_PATTERN',"
            "'LEARNING_CANDIDATE_READY'"
            ")",
            name="ck_content_performance_observation_status",
        ),
        sa.ForeignKeyConstraint(
            ["published_content_id"],
            ["published_contents.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_performance_observation_content",
        "content_performance_observations",
        ["published_content_id", "observed_at"],
        unique=False,
    )

    op.add_column(
        "content_experiments",
        sa.Column("content_item_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "content_experiments",
        sa.Column("content_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "content_experiments",
        sa.Column("published_content_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_content_experiments_content_item",
        "content_experiments",
        "content_items",
        ["content_item_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_content_experiments_content_version",
        "content_experiments",
        "content_versions",
        ["content_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_content_experiments_published_content",
        "content_experiments",
        "published_contents",
        ["published_content_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_content_experiment_content_version",
        "content_experiments",
        ["content_version_id"],
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION prevent_content_experiment_rebind()
            RETURNS trigger AS $pm01$
            BEGIN
                IF OLD.content_item_id IS NOT NULL
                   AND NEW.content_item_id IS DISTINCT FROM OLD.content_item_id THEN
                    RAISE EXCEPTION 'pm01_content_experiment_binding_is_immutable';
                END IF;
                IF OLD.content_version_id IS NOT NULL
                   AND NEW.content_version_id IS DISTINCT FROM OLD.content_version_id THEN
                    RAISE EXCEPTION 'pm01_content_experiment_binding_is_immutable';
                END IF;
                IF OLD.published_content_id IS NOT NULL
                   AND NEW.published_content_id IS DISTINCT FROM OLD.published_content_id THEN
                    RAISE EXCEPTION 'pm01_content_experiment_binding_is_immutable';
                END IF;
                IF OLD.content_version_id IS NOT NULL
                   AND (
                       NEW.project_id IS DISTINCT FROM OLD.project_id
                       OR NEW.content_opportunity_id
                          IS DISTINCT FROM OLD.content_opportunity_id
                       OR NEW.need_hypothesis_id
                          IS DISTINCT FROM OLD.need_hypothesis_id
                       OR NEW.hypothesis_version
                          IS DISTINCT FROM OLD.hypothesis_version
                       OR NEW.expected_behaviour
                          IS DISTINCT FROM OLD.expected_behaviour
                       OR NEW.measurement_plan_json
                          IS DISTINCT FROM OLD.measurement_plan_json
                       OR NEW.metric_definitions_json
                          IS DISTINCT FROM OLD.metric_definitions_json
                       OR NEW.minimum_evidence_json
                          IS DISTINCT FROM OLD.minimum_evidence_json
                       OR NEW.review_window_start
                          IS DISTINCT FROM OLD.review_window_start
                       OR NEW.review_window_end
                          IS DISTINCT FROM OLD.review_window_end
                   ) THEN
                    RAISE EXCEPTION 'pm01_content_experiment_contract_is_immutable';
                END IF;
                RETURN NEW;
            END;
            $pm01$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER content_experiment_binding_immutable
            BEFORE UPDATE OF content_item_id, content_version_id, published_content_id
            ON content_experiments
            FOR EACH ROW
            EXECUTE FUNCTION prevent_content_experiment_rebind()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_published_content_scope()
            RETURNS trigger AS $$
            DECLARE
                item_project uuid;
                version_item uuid;
            BEGIN
                SELECT project_id INTO item_project
                FROM content_items WHERE id = NEW.content_item_id;
                SELECT content_item_id INTO version_item
                FROM content_versions WHERE id = NEW.current_content_version_id;

                IF item_project IS NULL OR version_item IS NULL THEN
                    RAISE EXCEPTION 'pm01_publication_identity_missing';
                END IF;
                IF item_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'pm01_publication_project_mismatch';
                END IF;
                IF version_item IS DISTINCT FROM NEW.content_item_id THEN
                    RAISE EXCEPTION 'pm01_publication_version_item_mismatch';
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
            CREATE TRIGGER published_content_scope_guard
            BEFORE INSERT OR UPDATE OF
                project_id, content_item_id, current_content_version_id
            ON published_contents
            FOR EACH ROW
            EXECUTE FUNCTION validate_published_content_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_publish_event_scope()
            RETURNS trigger AS $$
            DECLARE
                mapped_item uuid;
                version_item uuid;
                experiment_version uuid;
            BEGIN
                SELECT content_item_id INTO mapped_item
                FROM published_contents WHERE id = NEW.published_content_id;
                SELECT content_item_id INTO version_item
                FROM content_versions WHERE id = NEW.content_version_id;
                SELECT content_version_id INTO experiment_version
                FROM content_experiments WHERE id = NEW.content_experiment_id;

                IF mapped_item IS NULL OR version_item IS NULL
                   OR experiment_version IS NULL THEN
                    RAISE EXCEPTION 'pm01_publish_event_identity_missing';
                END IF;
                IF mapped_item IS DISTINCT FROM version_item THEN
                    RAISE EXCEPTION 'pm01_publish_event_version_mismatch';
                END IF;
                IF experiment_version IS DISTINCT FROM NEW.content_version_id THEN
                    RAISE EXCEPTION 'pm01_publish_event_experiment_mismatch';
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
            CREATE TRIGGER publish_event_scope_guard
            BEFORE INSERT
            ON publish_events
            FOR EACH ROW
            EXECUTE FUNCTION validate_publish_event_scope()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION prevent_publish_event_mutation()
            RETURNS trigger AS $pm01$
            BEGIN
                RAISE EXCEPTION 'pm01_publish_event_is_immutable';
            END;
            $pm01$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER publish_events_immutable
            BEFORE UPDATE OR DELETE ON publish_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_publish_event_mutation()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_performance_identity()
            RETURNS trigger AS $$
            DECLARE
                mapped_item uuid;
                version_item uuid;
                has_publish_event boolean;
            BEGIN
                SELECT content_item_id INTO mapped_item
                FROM published_contents WHERE id = NEW.published_content_id;
                SELECT content_item_id INTO version_item
                FROM content_versions WHERE id = NEW.content_version_id;
                SELECT EXISTS(
                    SELECT 1
                    FROM publish_events
                    WHERE published_content_id = NEW.published_content_id
                      AND content_version_id = NEW.content_version_id
                ) INTO has_publish_event;

                IF mapped_item IS NULL OR version_item IS NULL THEN
                    RAISE EXCEPTION 'pm01_measurement_identity_missing';
                END IF;
                IF mapped_item IS DISTINCT FROM version_item THEN
                    RAISE EXCEPTION 'pm01_measurement_version_mismatch';
                END IF;
                IF NOT has_publish_event THEN
                    RAISE EXCEPTION 'pm01_measurement_publish_event_missing';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    for table_name in (
        "performance_snapshots",
        "performance_metrics",
        "content_performance_observations",
    ):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER {table_name}_identity_guard
                BEFORE INSERT OR UPDATE OF published_content_id, content_version_id
                ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION validate_performance_identity()
                """
            )
        )


def downgrade() -> None:
    for table_name in (
        "content_performance_observations",
        "performance_metrics",
        "performance_snapshots",
    ):
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS {table_name}_identity_guard ON {table_name}"
            )
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_performance_identity()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS publish_events_immutable ON publish_events"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS prevent_publish_event_mutation()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS publish_event_scope_guard ON publish_events"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_publish_event_scope()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS published_content_scope_guard ON published_contents"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_published_content_scope()"))

    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS content_experiment_binding_immutable "
            "ON content_experiments"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS prevent_content_experiment_rebind()"))
    op.drop_constraint(
        "uq_content_experiment_content_version",
        "content_experiments",
        type_="unique",
    )
    op.drop_constraint(
        "fk_content_experiments_published_content",
        "content_experiments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_content_experiments_content_version",
        "content_experiments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_content_experiments_content_item",
        "content_experiments",
        type_="foreignkey",
    )
    op.drop_column("content_experiments", "published_content_id")
    op.drop_column("content_experiments", "content_version_id")
    op.drop_column("content_experiments", "content_item_id")

    op.drop_index(
        "ix_content_performance_observation_content",
        table_name="content_performance_observations",
    )
    op.drop_table("content_performance_observations")
    op.drop_index(
        "ix_performance_metrics_content_name_date",
        table_name="performance_metrics",
    )
    op.drop_table("performance_metrics")
    op.drop_index(
        "ix_performance_snapshots_published_window",
        table_name="performance_snapshots",
    )
    op.drop_table("performance_snapshots")
    op.drop_index(
        "ix_publish_events_experiment",
        table_name="publish_events",
    )
    op.drop_index(
        "ix_publish_events_content_version",
        table_name="publish_events",
    )
    op.drop_table("publish_events")
    op.drop_index(
        "ix_published_contents_project_url",
        table_name="published_contents",
    )
    op.drop_table("published_contents")

    op.drop_constraint("ck_content_run_mode", "content_runs", type_="check")
    op.create_check_constraint(
        "ck_content_run_mode",
        "content_runs",
        "run_mode in ('create','update','refresh','localize','eval')",
    )