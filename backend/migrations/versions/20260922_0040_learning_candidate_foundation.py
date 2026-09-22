"""Add LL-01B learning candidate foundation.

Revision ID: 20260922_0040
Revises: 20260922_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0040"
down_revision: str | None = "20260922_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_learning_guards() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_learning_assessment_artifact()
            RETURNS trigger AS $
            DECLARE
                run_project uuid;
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NEW.artifact_type = 'learning_assessment' THEN
                        SELECT project_id INTO run_project
                        FROM content_runs
                        WHERE id = NEW.run_id;

                        IF run_project IS NULL
                           OR NEW.content_json IS NULL
                           OR NEW.content_json->>'project_id'
                              IS DISTINCT FROM run_project::text
                           OR NEW.step_run_id IS NOT NULL THEN
                            RAISE EXCEPTION
                                'learning_assessment_artifact_lineage_invalid';
                        END IF;
                    END IF;
                    RETURN NEW;
                END IF;

                IF TG_OP = 'DELETE' THEN
                    IF OLD.artifact_type = 'learning_assessment' THEN
                        RAISE EXCEPTION
                            'learning_assessment_artifact_delete_forbidden';
                    END IF;
                    RETURN OLD;
                END IF;

                IF OLD.artifact_type = 'learning_assessment'
                   OR NEW.artifact_type = 'learning_assessment' THEN
                    RAISE EXCEPTION
                        'learning_assessment_artifact_update_forbidden';
                END IF;
                RETURN NEW;
            END;
            $ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER learning_assessment_artifact_guard
            BEFORE INSERT OR UPDATE OR DELETE ON artifacts
            FOR EACH ROW
            EXECUTE FUNCTION protect_learning_assessment_artifact()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_learning_candidate()
            RETURNS trigger AS $$
            DECLARE
                target_project uuid;
                assessment_type text;
                assessment_project text;
                prior_project uuid;
                prior_key text;
                prior_version integer;
                prior_status text;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'learning_candidate_delete_forbidden';
                END IF;

                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'OPEN' THEN
                        RAISE EXCEPTION
                            'learning_candidate_initial_status_must_be_open';
                    END IF;

                    SELECT artifact_type, content_json->>'project_id'
                    INTO assessment_type, assessment_project
                    FROM artifacts
                    WHERE id = NEW.source_assessment_artifact_id;

                    IF assessment_type IS DISTINCT FROM 'learning_assessment'
                       OR assessment_project IS DISTINCT FROM NEW.project_id::text THEN
                        RAISE EXCEPTION
                            'learning_candidate_assessment_project_mismatch';
                    END IF;

                    IF NEW.target_type = 'new_customer_insight' THEN
                        IF NEW.proposal_json::jsonb = '{}'::jsonb THEN
                            RAISE EXCEPTION
                                'learning_candidate_proposal_required';
                        END IF;
                    ELSE
                        IF NEW.proposal_json::jsonb <> '{}'::jsonb THEN
                            RAISE EXCEPTION
                                'learning_candidate_proposal_unexpected';
                        END IF;
                    END IF;

                    IF NEW.target_type = 'need_hypothesis' THEN
                        IF NEW.target_id IS NULL THEN
                            RAISE EXCEPTION
                                'learning_candidate_target_required';
                        END IF;
                        SELECT project_id INTO target_project
                        FROM need_hypotheses
                        WHERE id = NEW.target_id;
                    ELSIF NEW.target_type = 'customer_insight' THEN
                        IF NEW.target_id IS NULL THEN
                            RAISE EXCEPTION
                                'learning_candidate_target_required';
                        END IF;
                        SELECT project_id INTO target_project
                        FROM customer_insights
                        WHERE id = NEW.target_id;
                    ELSE
                        IF NEW.target_id IS NOT NULL THEN
                            RAISE EXCEPTION
                                'learning_candidate_target_must_be_null';
                        END IF;
                        target_project := NEW.project_id;
                    END IF;

                    IF target_project IS NULL THEN
                        RAISE EXCEPTION 'learning_candidate_target_not_found';
                    END IF;
                    IF target_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION
                            'learning_candidate_target_project_mismatch';
                    END IF;

                    IF NEW.version = 1 THEN
                        IF NEW.supersedes_id IS NOT NULL THEN
                            RAISE EXCEPTION
                                'learning_candidate_v1_cannot_supersede';
                        END IF;
                    ELSE
                        IF NEW.supersedes_id IS NULL THEN
                            RAISE EXCEPTION
                                'learning_candidate_supersedes_required';
                        END IF;
                        SELECT project_id, candidate_key, version, status
                        INTO prior_project, prior_key, prior_version, prior_status
                        FROM learning_candidates
                        WHERE id = NEW.supersedes_id;

                        IF prior_project IS NULL
                           OR prior_project IS DISTINCT FROM NEW.project_id
                           OR prior_key IS DISTINCT FROM NEW.candidate_key
                           OR prior_version IS DISTINCT FROM NEW.version - 1
                           OR prior_status IS DISTINCT FROM 'OPEN' THEN
                            RAISE EXCEPTION
                                'learning_candidate_supersedes_invalid';
                        END IF;
                    END IF;

                    RETURN NEW;
                END IF;

                IF OLD.project_id IS DISTINCT FROM NEW.project_id
                   OR OLD.candidate_key IS DISTINCT FROM NEW.candidate_key
                   OR OLD.version IS DISTINCT FROM NEW.version
                   OR OLD.target_type IS DISTINCT FROM NEW.target_type
                   OR OLD.target_id IS DISTINCT FROM NEW.target_id
                   OR OLD.statement IS DISTINCT FROM NEW.statement
                   OR OLD.relation IS DISTINCT FROM NEW.relation
                   OR OLD.proposal_json::jsonb IS DISTINCT FROM NEW.proposal_json::jsonb
                   OR OLD.scope_json::jsonb IS DISTINCT FROM NEW.scope_json::jsonb
                   OR OLD.evidence_status IS DISTINCT FROM NEW.evidence_status
                   OR OLD.alternative_explanations_json::jsonb
                      IS DISTINCT FROM NEW.alternative_explanations_json::jsonb
                   OR OLD.missing_evidence_json::jsonb
                      IS DISTINCT FROM NEW.missing_evidence_json::jsonb
                   OR OLD.expected_benefit IS DISTINCT FROM NEW.expected_benefit
                   OR OLD.regression_risk IS DISTINCT FROM NEW.regression_risk
                   OR OLD.source_assessment_artifact_id
                      IS DISTINCT FROM NEW.source_assessment_artifact_id
                   OR OLD.supersedes_id IS DISTINCT FROM NEW.supersedes_id THEN
                    RAISE EXCEPTION
                        'learning_candidate_version_content_immutable';
                END IF;

                IF OLD.status IS DISTINCT FROM NEW.status THEN
                    IF OLD.status <> 'OPEN'
                       OR NEW.status NOT IN ('SUPERSEDED','ARCHIVED') THEN
                        RAISE EXCEPTION
                            'learning_candidate_status_transition_invalid';
                    END IF;
                    IF NEW.status = 'SUPERSEDED'
                       AND NOT EXISTS(
                           SELECT 1
                           FROM learning_candidates newer
                           WHERE newer.supersedes_id = OLD.id
                             AND newer.project_id = OLD.project_id
                             AND newer.candidate_key = OLD.candidate_key
                             AND newer.version = OLD.version + 1
                       ) THEN
                        RAISE EXCEPTION
                            'learning_candidate_newer_version_required';
                    END IF;
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
            CREATE TRIGGER learning_candidates_guard
            BEFORE INSERT OR UPDATE OR DELETE ON learning_candidates
            FOR EACH ROW
            EXECUTE FUNCTION validate_learning_candidate()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION supersede_prior_learning_candidate()
            RETURNS trigger AS $
            BEGIN
                IF NEW.supersedes_id IS NOT NULL THEN
                    UPDATE learning_candidates
                    SET status = 'SUPERSEDED',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.supersedes_id
                      AND status = 'OPEN';

                    IF NOT FOUND THEN
                        RAISE EXCEPTION
                            'learning_candidate_prior_not_open';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER learning_candidate_auto_supersede
            AFTER INSERT ON learning_candidates
            FOR EACH ROW
            EXECUTE FUNCTION supersede_prior_learning_candidate()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_learning_candidate_assessment()
            RETURNS trigger AS $$
            DECLARE
                candidate_project uuid;
                assessment_type text;
                assessment_project text;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_assessment_update_forbidden';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_assessment_delete_forbidden';
                END IF;

                SELECT project_id INTO candidate_project
                FROM learning_candidates
                WHERE id = NEW.learning_candidate_id;
                SELECT artifact_type, content_json->>'project_id'
                INTO assessment_type, assessment_project
                FROM artifacts
                WHERE id = NEW.assessment_artifact_id;

                IF candidate_project IS NULL
                   OR assessment_type IS DISTINCT FROM 'learning_assessment'
                   OR assessment_project IS DISTINCT FROM candidate_project::text THEN
                    RAISE EXCEPTION
                        'learning_candidate_assessment_project_mismatch';
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
            CREATE TRIGGER learning_candidate_assessments_guard
            BEFORE INSERT OR UPDATE OR DELETE ON learning_candidate_assessments
            FOR EACH ROW
            EXECUTE FUNCTION validate_learning_candidate_assessment()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_learning_candidate_signal()
            RETURNS trigger AS $$
            DECLARE
                candidate_project uuid;
                signal_project uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_signal_update_forbidden';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_signal_delete_forbidden';
                END IF;

                SELECT project_id INTO candidate_project
                FROM learning_candidates
                WHERE id = NEW.learning_candidate_id;
                SELECT project_id INTO signal_project
                FROM signals
                WHERE id = NEW.signal_id;

                IF candidate_project IS NULL OR signal_project IS NULL THEN
                    RAISE EXCEPTION
                        'learning_candidate_signal_not_found';
                END IF;
                IF candidate_project IS DISTINCT FROM signal_project THEN
                    RAISE EXCEPTION
                        'learning_candidate_signal_project_mismatch';
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
            CREATE TRIGGER learning_candidate_signals_guard
            BEFORE INSERT OR UPDATE OR DELETE ON learning_candidate_signals
            FOR EACH ROW
            EXECUTE FUNCTION validate_learning_candidate_signal()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_learning_candidate_observation()
            RETURNS trigger AS $$
            DECLARE
                candidate_project uuid;
                observation_project uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_observation_update_forbidden';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'learning_candidate_observation_delete_forbidden';
                END IF;

                SELECT project_id INTO candidate_project
                FROM learning_candidates
                WHERE id = NEW.learning_candidate_id;

                SELECT pc.project_id INTO observation_project
                FROM content_performance_observations o
                JOIN published_contents pc
                  ON pc.id = o.published_content_id
                WHERE o.id = NEW.observation_id;

                IF candidate_project IS NULL OR observation_project IS NULL THEN
                    RAISE EXCEPTION
                        'learning_candidate_observation_not_found';
                END IF;
                IF candidate_project IS DISTINCT FROM observation_project THEN
                    RAISE EXCEPTION
                        'learning_candidate_observation_project_mismatch';
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
            CREATE TRIGGER learning_candidate_observations_guard
            BEFORE INSERT OR UPDATE OR DELETE ON learning_candidate_observations
            FOR EACH ROW
            EXECUTE FUNCTION validate_learning_candidate_observation()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "learning_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.Column("proposal_json", sa.JSON(), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("alternative_explanations_json", sa.JSON(), nullable=False),
        sa.Column("missing_evidence_json", sa.JSON(), nullable=False),
        sa.Column("expected_benefit", sa.Text(), nullable=True),
        sa.Column("regression_risk", sa.Text(), nullable=True),
        sa.Column("source_assessment_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_key ~ '^[0-9a-f]{64}$'",
            name="ck_learning_candidates_key",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_learning_candidates_version_positive",
        ),
        sa.CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_candidates_target_type",
        ),
        sa.CheckConstraint(
            "relation in ('supports','contradicts','context','proposes','no_change')",
            name="ck_learning_candidates_relation",
        ),
        sa.CheckConstraint(
            "evidence_status in "
            "('NEEDS_EVIDENCE','EARLY_SIGNAL','REPEATED_PATTERN',"
            "'CONTESTED','READY_FOR_REVIEW')",
            name="ck_learning_candidates_evidence_status",
        ),
        sa.CheckConstraint(
            "status in ('OPEN','SUPERSEDED','ARCHIVED')",
            name="ck_learning_candidates_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["source_assessment_artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["learning_candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "candidate_key",
            "version",
            name="uq_learning_candidate_project_key_version",
        ),
    )
    op.create_index(
        "ix_learning_candidates_project_status",
        "learning_candidates",
        ["project_id", "status", "evidence_status"],
        unique=False,
    )
    op.create_index(
        "ix_learning_candidates_target",
        "learning_candidates",
        ["target_type", "target_id"],
        unique=False,
    )

    op.create_table(
        "learning_candidate_assessments",
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_artifact_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_artifact_id"],
            ["artifacts.id"],
        ),
        sa.PrimaryKeyConstraint(
            "learning_candidate_id",
            "assessment_artifact_id",
        ),
    )
    op.create_index(
        "ix_learning_candidate_assessments_artifact",
        "learning_candidate_assessments",
        ["assessment_artifact_id", "learning_candidate_id"],
        unique=False,
    )

    op.create_table(
        "learning_candidate_signals",
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_learning_candidate_signals_relation",
        ),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("learning_candidate_id", "signal_id"),
    )
    op.create_index(
        "ix_learning_candidate_signals_signal",
        "learning_candidate_signals",
        ["signal_id", "relation"],
        unique=False,
    )

    op.create_table(
        "learning_candidate_observations",
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_learning_candidate_observations_relation",
        ),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["content_performance_observations.id"],
        ),
        sa.PrimaryKeyConstraint(
            "learning_candidate_id",
            "observation_id",
        ),
    )
    op.create_index(
        "ix_learning_candidate_observations_observation",
        "learning_candidate_observations",
        ["observation_id", "relation"],
        unique=False,
    )

    _create_learning_guards()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_candidate_observations_guard "
            "ON learning_candidate_observations"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_learning_candidate_observation()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_candidate_signals_guard "
            "ON learning_candidate_signals"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_learning_candidate_signal()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_candidate_assessments_guard "
            "ON learning_candidate_assessments"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_learning_candidate_assessment()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_candidate_auto_supersede "
            "ON learning_candidates"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS supersede_prior_learning_candidate()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_candidates_guard "
            "ON learning_candidates"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_learning_candidate()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS learning_assessment_artifact_guard "
            "ON artifacts"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS protect_learning_assessment_artifact()")
    )

    op.drop_index(
        "ix_learning_candidate_observations_observation",
        table_name="learning_candidate_observations",
    )
    op.drop_table("learning_candidate_observations")
    op.drop_index(
        "ix_learning_candidate_signals_signal",
        table_name="learning_candidate_signals",
    )
    op.drop_table("learning_candidate_signals")
    op.drop_index(
        "ix_learning_candidate_assessments_artifact",
        table_name="learning_candidate_assessments",
    )
    op.drop_table("learning_candidate_assessments")
    op.drop_index(
        "ix_learning_candidates_target",
        table_name="learning_candidates",
    )
    op.drop_index(
        "ix_learning_candidates_project_status",
        table_name="learning_candidates",
    )
    op.drop_table("learning_candidates")