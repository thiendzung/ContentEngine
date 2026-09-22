"""Add LL-01C human learning review and application receipts.

Revision ID: 20260922_0041
Revises: 20260922_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0041"
down_revision: str | None = "20260922_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION learning_candidate_target_snapshot(
            p_candidate_id uuid
        ) RETURNS jsonb AS $$
        DECLARE
            candidate learning_candidates%ROWTYPE;
            need need_hypotheses%ROWTYPE;
            insight customer_insights%ROWTYPE;
            frozen_need_id uuid;
            frozen_need_version integer;
            frozen_audience uuid;
            latest_insight_version integer;
            current_target jsonb;
        BEGIN
            SELECT * INTO candidate
            FROM learning_candidates
            WHERE id = p_candidate_id;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'learning_candidate_snapshot_candidate_not_found';
            END IF;

            frozen_need_id := NULLIF(
                candidate.scope_json->>'need_hypothesis_id',
                ''
            )::uuid;
            frozen_need_version := NULLIF(
                candidate.scope_json->>'need_hypothesis_version',
                ''
            )::integer;
            frozen_audience := NULLIF(
                candidate.scope_json->>'audience_hypothesis_id',
                ''
            )::uuid;

            IF frozen_need_id IS NULL OR frozen_need_version IS NULL THEN
                RAISE EXCEPTION 'learning_candidate_snapshot_scope_invalid';
            END IF;

            IF candidate.target_type = 'need_hypothesis' THEN
                IF candidate.target_id IS DISTINCT FROM frozen_need_id THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_need_target_mismatch';
                END IF;

                SELECT * INTO need
                FROM need_hypotheses
                WHERE id = candidate.target_id;

                IF NOT FOUND
                   OR need.project_id IS DISTINCT FROM candidate.project_id
                   OR need.version IS DISTINCT FROM frozen_need_version
                   OR need.audience_hypothesis_id IS DISTINCT FROM frozen_audience THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_need_stale';
                END IF;

                current_target := jsonb_build_object(
                    'id', need.id::text,
                    'version', need.version,
                    'status', need.status,
                    'audience_hypothesis_id',
                        CASE
                            WHEN need.audience_hypothesis_id IS NULL THEN NULL
                            ELSE need.audience_hypothesis_id::text
                        END
                );
            ELSIF candidate.target_type = 'customer_insight' THEN
                IF candidate.target_id IS NULL THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_insight_target_missing';
                END IF;

                SELECT * INTO insight
                FROM customer_insights
                WHERE id = candidate.target_id;

                IF NOT FOUND
                   OR insight.project_id IS DISTINCT FROM candidate.project_id
                   OR insight.audience_hypothesis_id IS DISTINCT FROM frozen_audience THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_insight_stale';
                END IF;

                SELECT max(ci.version)
                INTO latest_insight_version
                FROM customer_insights AS ci
                WHERE ci.project_id = insight.project_id
                  AND ci.insight_key = insight.insight_key;

                IF latest_insight_version IS DISTINCT FROM insight.version THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_insight_version_stale';
                END IF;

                current_target := jsonb_build_object(
                    'id', insight.id::text,
                    'insight_key', insight.insight_key,
                    'version', insight.version,
                    'status', insight.status,
                    'audience_hypothesis_id',
                        CASE
                            WHEN insight.audience_hypothesis_id IS NULL THEN NULL
                            ELSE insight.audience_hypothesis_id::text
                        END
                );
            ELSIF candidate.target_type = 'new_customer_insight' THEN
                IF candidate.target_id IS NOT NULL THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_new_insight_target_invalid';
                END IF;

                SELECT * INTO need
                FROM need_hypotheses
                WHERE id = frozen_need_id;

                IF NOT FOUND
                   OR need.project_id IS DISTINCT FROM candidate.project_id
                   OR need.version IS DISTINCT FROM frozen_need_version
                   OR need.audience_hypothesis_id IS DISTINCT FROM frozen_audience THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_new_insight_need_stale';
                END IF;

                current_target := jsonb_build_object(
                    'need_hypothesis_id', need.id::text,
                    'need_version', need.version,
                    'need_status', need.status,
                    'audience_hypothesis_id',
                        CASE
                            WHEN need.audience_hypothesis_id IS NULL THEN NULL
                            ELSE need.audience_hypothesis_id::text
                        END
                );
            ELSIF candidate.target_type = 'no_map_change' THEN
                IF candidate.target_id IS NOT NULL THEN
                    RAISE EXCEPTION 'learning_candidate_snapshot_no_map_target_invalid';
                END IF;
                current_target := 'null'::jsonb;
            ELSE
                RAISE EXCEPTION 'learning_candidate_snapshot_target_type_invalid';
            END IF;

            RETURN jsonb_build_object(
                'target_type', candidate.target_type,
                'target_id',
                    CASE
                        WHEN candidate.target_id IS NULL THEN NULL
                        ELSE candidate.target_id::text
                    END,
                'relation', candidate.relation,
                'proposal', candidate.proposal_json::jsonb,
                'scope', candidate.scope_json::jsonb,
                'evidence_status', candidate.evidence_status,
                'current_target', current_target
            );
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    op.execute(
        """
        CREATE FUNCTION learning_candidate_snapshot_hash(
            p_candidate_id uuid
        ) RETURNS text AS $$
        DECLARE
            payload jsonb;
        BEGIN
            SELECT jsonb_build_object(
                'candidate',
                    jsonb_build_object(
                        'id', lc.id::text,
                        'project_id', lc.project_id::text,
                        'candidate_key', lc.candidate_key,
                        'version', lc.version,
                        'target_type', lc.target_type,
                        'target_id',
                            CASE
                                WHEN lc.target_id IS NULL THEN NULL
                                ELSE lc.target_id::text
                            END,
                        'statement', lc.statement,
                        'relation', lc.relation,
                        'proposal', lc.proposal_json::jsonb,
                        'scope', lc.scope_json::jsonb,
                        'evidence_status', lc.evidence_status,
                        'alternative_explanations',
                            lc.alternative_explanations_json::jsonb,
                        'missing_evidence', lc.missing_evidence_json::jsonb,
                        'expected_benefit', lc.expected_benefit,
                        'regression_risk', lc.regression_risk,
                        'source_assessment_artifact_id',
                            lc.source_assessment_artifact_id::text,
                        'supersedes_id',
                            CASE
                                WHEN lc.supersedes_id IS NULL THEN NULL
                                ELSE lc.supersedes_id::text
                            END,
                        'status', lc.status
                    ),
                'assessments',
                    COALESCE(
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'id', a.id::text,
                                    'content_hash', a.content_hash
                                )
                                ORDER BY a.id::text
                            )
                            FROM learning_candidate_assessments AS lca
                            JOIN artifacts AS a
                              ON a.id = lca.assessment_artifact_id
                            WHERE lca.learning_candidate_id = lc.id
                        ),
                        '[]'::jsonb
                    ),
                'signals',
                    COALESCE(
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'id', s.id::text,
                                    'relation', lcs.relation,
                                    'fingerprint', s.fingerprint,
                                    'independence_group', s.independence_group,
                                    'duplicate_of_id',
                                        CASE
                                            WHEN s.duplicate_of_id IS NULL THEN NULL
                                            ELSE s.duplicate_of_id::text
                                        END
                                )
                                ORDER BY s.id::text, lcs.relation
                            )
                            FROM learning_candidate_signals AS lcs
                            JOIN signals AS s
                              ON s.id = lcs.signal_id
                            WHERE lcs.learning_candidate_id = lc.id
                        ),
                        '[]'::jsonb
                    ),
                'observations',
                    COALESCE(
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'id', lco.observation_id::text,
                                    'relation', lco.relation
                                )
                                ORDER BY lco.observation_id::text, lco.relation
                            )
                            FROM learning_candidate_observations AS lco
                            WHERE lco.learning_candidate_id = lc.id
                        ),
                        '[]'::jsonb
                    ),
                'target_snapshot',
                    learning_candidate_target_snapshot(lc.id)
            )
            INTO payload
            FROM learning_candidates AS lc
            WHERE lc.id = p_candidate_id;

            IF payload IS NULL THEN
                RAISE EXCEPTION 'learning_candidate_snapshot_candidate_not_found';
            END IF;

            RETURN encode(
                sha256(convert_to(payload::text, 'UTF8')),
                'hex'
            );
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    op.execute(
        """
        CREATE FUNCTION learning_candidate_applied_signal_refs(
            p_candidate_id uuid
        ) RETURNS jsonb AS $$
            SELECT COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'signal_id', lcs.signal_id::text,
                        'relation', lcs.relation
                    )
                    ORDER BY lcs.signal_id::text, lcs.relation
                ),
                '[]'::jsonb
            )
            FROM learning_candidate_signals AS lcs
            JOIN learning_candidates AS lc
              ON lc.id = lcs.learning_candidate_id
            WHERE lcs.learning_candidate_id = p_candidate_id
              AND lc.target_type <> 'no_map_change'
              AND (
                    lc.target_type <> 'need_hypothesis'
                    OR lcs.relation IN ('supports','contradicts')
              )
        $$ LANGUAGE sql STABLE
        """
    )

    op.execute(
        """
        CREATE FUNCTION serialize_customer_insight_project()
        RETURNS trigger AS $$
        BEGIN
            PERFORM 1
            FROM projects
            WHERE id = NEW.project_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'customer_insight_project_not_found';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER ll01c_customer_insight_project_lock
        BEFORE INSERT ON customer_insights
        FOR EACH ROW
        EXECUTE FUNCTION serialize_customer_insight_project()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_learning_candidate_review()
        RETURNS trigger AS $$
        DECLARE
            candidate_project uuid;
            candidate_version integer;
            candidate_status text;
            v_candidate_key text;
            candidate_target_type text;
            candidate_evidence_status text;
            canonical_snapshot_hash text;
            canonical_target_snapshot jsonb;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_candidate_review_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_candidate_review_delete_forbidden';
            END IF;

            SELECT lc.project_id, lc.version, lc.status, lc.candidate_key,
                   lc.target_type, lc.evidence_status
            INTO candidate_project, candidate_version, candidate_status,
                 v_candidate_key, candidate_target_type, candidate_evidence_status
            FROM learning_candidates AS lc
            WHERE lc.id = NEW.learning_candidate_id;

            IF candidate_project IS NULL THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_not_found';
            END IF;
            IF candidate_project IS DISTINCT FROM NEW.project_id
               OR candidate_version IS DISTINCT FROM NEW.candidate_version THEN
                RAISE EXCEPTION 'learning_candidate_review_identity_mismatch';
            END IF;
            IF candidate_status IS DISTINCT FROM 'OPEN' THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_not_open';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM learning_candidates newer
                WHERE newer.project_id = candidate_project
                  AND newer.candidate_key = v_candidate_key
                  AND newer.version > candidate_version
            ) THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_stale';
            END IF;

            canonical_snapshot_hash :=
                learning_candidate_snapshot_hash(NEW.learning_candidate_id);
            canonical_target_snapshot :=
                learning_candidate_target_snapshot(NEW.learning_candidate_id);

            IF NEW.candidate_snapshot_hash
                   IS DISTINCT FROM canonical_snapshot_hash
               OR NEW.target_snapshot_json::jsonb
                   IS DISTINCT FROM canonical_target_snapshot THEN
                RAISE EXCEPTION 'learning_candidate_review_snapshot_mismatch';
            END IF;

            IF length(btrim(NEW.reviewed_by)) = 0
               OR length(btrim(NEW.reason)) = 0 THEN
                RAISE EXCEPTION 'learning_candidate_review_human_fields_required';
            END IF;
            IF NEW.decision = 'APPROVE'
               AND candidate_target_type <> 'no_map_change'
               AND candidate_evidence_status = 'NEEDS_EVIDENCE' THEN
                RAISE EXCEPTION 'learning_candidate_review_evidence_required';
            END IF;
            IF NEW.decision = 'APPROVE'
               AND candidate_target_type = 'need_hypothesis'
               AND NOT EXISTS (
                   SELECT 1
                   FROM learning_candidate_signals evidence
                   WHERE evidence.learning_candidate_id = NEW.learning_candidate_id
                     AND evidence.relation IN ('supports','contradicts')
               ) THEN
                RAISE EXCEPTION 'learning_candidate_review_need_directional_evidence_required';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_candidate_reviews_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_candidate_reviews
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_candidate_review()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_learning_application()
        RETURNS trigger AS $$
        DECLARE
            candidate_project uuid;
            candidate_version integer;
            candidate_status text;
            v_candidate_key text;
            candidate_target_type text;
            candidate_target_id uuid;
            candidate_scope jsonb;
            review_project uuid;
            snapshot_project uuid;
            snapshot_hash text;
            snapshot_type text;
            review_candidate uuid;
            review_version integer;
            review_decision text;
            review_snapshot text;
            review_target_snapshot jsonb;
            canonical_snapshot_hash text;
            canonical_target_snapshot jsonb;
            expected_signal_refs jsonb;
            candidate_statement text;
            candidate_proposal jsonb;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_application_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_application_delete_forbidden';
            END IF;

            SELECT lc.project_id, lc.version, lc.status, lc.candidate_key,
                   lc.target_type, lc.target_id, lc.scope_json::jsonb,
                   lc.statement, lc.proposal_json::jsonb
            INTO candidate_project, candidate_version, candidate_status,
                 v_candidate_key, candidate_target_type, candidate_target_id,
                 candidate_scope, candidate_statement, candidate_proposal
            FROM learning_candidates AS lc
            WHERE lc.id = NEW.learning_candidate_id;

            SELECT r.project_id, r.learning_candidate_id, r.candidate_version,
                   r.decision, r.candidate_snapshot_hash,
                   r.target_snapshot_json::jsonb
            INTO review_project, review_candidate, review_version,
                 review_decision, review_snapshot, review_target_snapshot
            FROM learning_candidate_reviews AS r
            WHERE r.id = NEW.review_id;

            IF candidate_project IS NULL OR review_project IS NULL THEN
                RAISE EXCEPTION 'learning_application_lineage_not_found';
            END IF;
            IF candidate_project IS DISTINCT FROM NEW.project_id
               OR candidate_version IS DISTINCT FROM NEW.candidate_version
               OR review_project IS DISTINCT FROM NEW.project_id
               OR review_candidate IS DISTINCT FROM NEW.learning_candidate_id
               OR review_version IS DISTINCT FROM NEW.candidate_version
               OR review_snapshot IS DISTINCT FROM NEW.candidate_snapshot_hash THEN
                RAISE EXCEPTION 'learning_application_identity_mismatch';
            END IF;
            IF candidate_status IS DISTINCT FROM 'OPEN' THEN
                RAISE EXCEPTION 'learning_application_candidate_not_open';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM learning_candidates newer
                WHERE newer.project_id = candidate_project
                  AND newer.candidate_key = v_candidate_key
                  AND newer.version > candidate_version
            ) THEN
                RAISE EXCEPTION 'learning_application_candidate_stale';
            END IF;

            canonical_snapshot_hash :=
                learning_candidate_snapshot_hash(NEW.learning_candidate_id);
            canonical_target_snapshot :=
                learning_candidate_target_snapshot(NEW.learning_candidate_id);

            IF review_snapshot IS DISTINCT FROM canonical_snapshot_hash
               OR review_target_snapshot
                    IS DISTINCT FROM canonical_target_snapshot THEN
                RAISE EXCEPTION 'learning_application_review_snapshot_stale';
            END IF;

            IF review_decision NOT IN ('APPROVE','NO_MAP_CHANGE') THEN
                RAISE EXCEPTION 'learning_application_review_not_applicable';
            END IF;
            IF NEW.target_type IS DISTINCT FROM candidate_target_type
               OR NEW.target_id IS DISTINCT FROM candidate_target_id THEN
                RAISE EXCEPTION 'learning_application_target_mismatch';
            END IF;
            IF NEW.frozen_scope_json::jsonb IS DISTINCT FROM candidate_scope THEN
                RAISE EXCEPTION 'learning_application_scope_mismatch';
            END IF;
            IF review_decision = 'NO_MAP_CHANGE'
               OR NEW.target_type = 'no_map_change' THEN
                IF NEW.applied_action IS DISTINCT FROM 'no_map_change'
                   OR NEW.resulting_target_id IS NOT NULL
                   OR NEW.customer_map_snapshot_artifact_id IS NOT NULL
                   OR NEW.before_state_hash IS NOT NULL
                   OR NEW.after_state_hash IS NOT NULL
                   OR NEW.change_report_json IS NOT NULL
                   OR json_array_length(NEW.applied_signal_refs_json) <> 0 THEN
                    RAISE EXCEPTION 'learning_application_no_map_change_invalid';
                END IF;
            ELSE
                IF review_decision IS DISTINCT FROM 'APPROVE'
                   OR NEW.resulting_target_id IS NULL
                   OR NEW.customer_map_snapshot_artifact_id IS NULL
                   OR NEW.before_state_hash IS NULL
                   OR NEW.after_state_hash IS NULL
                   OR NEW.change_report_json IS NULL
                   OR json_array_length(NEW.applied_signal_refs_json) = 0 THEN
                    RAISE EXCEPTION 'learning_application_mutation_receipt_incomplete';
                END IF;

                expected_signal_refs :=
                    learning_candidate_applied_signal_refs(
                        NEW.learning_candidate_id
                    );
                IF NEW.applied_signal_refs_json::jsonb
                     IS DISTINCT FROM expected_signal_refs THEN
                    RAISE EXCEPTION 'learning_application_signal_refs_mismatch';
                END IF;

                SELECT run.project_id, artifact.content_hash,
                       artifact.artifact_type
                INTO snapshot_project, snapshot_hash, snapshot_type
                FROM artifacts AS artifact
                JOIN content_runs AS run ON run.id = artifact.run_id
                WHERE artifact.id = NEW.customer_map_snapshot_artifact_id;

                IF snapshot_project IS NULL
                   OR snapshot_project IS DISTINCT FROM NEW.project_id
                   OR snapshot_type IS DISTINCT FROM 'customer_map_snapshot'
                   OR snapshot_hash IS DISTINCT FROM NEW.after_state_hash
                   OR NEW.change_report_json->>'current_snapshot_hash'
                      IS DISTINCT FROM NEW.after_state_hash
                   OR NEW.change_report_json->>'previous_snapshot_hash'
                      IS DISTINCT FROM NEW.before_state_hash THEN
                    RAISE EXCEPTION 'learning_application_snapshot_mismatch';
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM artifacts AS before_artifact
                    JOIN content_runs AS before_run
                      ON before_run.id = before_artifact.run_id
                    WHERE before_run.project_id = NEW.project_id
                      AND before_artifact.artifact_type = 'customer_map_snapshot'
                      AND before_artifact.content_hash = NEW.before_state_hash
                ) THEN
                    RAISE EXCEPTION 'learning_application_before_snapshot_missing';
                END IF;

                IF NEW.target_type = 'need_hypothesis' THEN
                    IF NEW.applied_action IS DISTINCT FROM 'link_need_signals'
                       OR NEW.resulting_target_id
                            IS DISTINCT FROM candidate_target_id THEN
                        RAISE EXCEPTION 'learning_application_action_mismatch';
                    END IF;
                    IF EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(expected_signal_refs) AS ref
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM need_hypothesis_signals AS nhs
                            WHERE nhs.need_hypothesis_id =
                                      NEW.resulting_target_id
                              AND nhs.signal_id =
                                      (ref->>'signal_id')::uuid
                              AND nhs.relation = ref->>'relation'
                        )
                    ) THEN
                        RAISE EXCEPTION 'learning_application_truth_links_missing';
                    END IF;
                ELSIF NEW.target_type = 'customer_insight' THEN
                    IF NEW.applied_action IS DISTINCT FROM 'link_insight_signals'
                       OR NEW.resulting_target_id
                            IS DISTINCT FROM candidate_target_id THEN
                        RAISE EXCEPTION 'learning_application_action_mismatch';
                    END IF;
                    IF EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(expected_signal_refs) AS ref
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM customer_insight_signals AS cis
                            WHERE cis.customer_insight_id =
                                      NEW.resulting_target_id
                              AND cis.signal_id =
                                      (ref->>'signal_id')::uuid
                              AND cis.relation = ref->>'relation'
                        )
                    ) THEN
                        RAISE EXCEPTION 'learning_application_truth_links_missing';
                    END IF;
                ELSIF NEW.target_type = 'new_customer_insight' THEN
                    IF NEW.applied_action
                         IS DISTINCT FROM 'create_candidate_insight' THEN
                        RAISE EXCEPTION 'learning_application_action_mismatch';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM customer_insights AS ci
                        WHERE ci.id = NEW.resulting_target_id
                          AND ci.project_id = NEW.project_id
                          AND ci.status = 'CANDIDATE'
                          AND ci.statement = candidate_statement
                          AND ci.insight_type =
                                candidate_proposal->>'insight_type'
                          AND ci.situation IS NOT DISTINCT FROM
                                candidate_proposal->>'situation'
                          AND ci.audience_hypothesis_id IS NOT DISTINCT FROM
                                NULLIF(
                                    candidate_scope->>'audience_hypothesis_id',
                                    ''
                                )::uuid
                    ) THEN
                        RAISE EXCEPTION 'learning_application_result_target_mismatch';
                    END IF;
                    IF EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(expected_signal_refs) AS ref
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM customer_insight_signals AS cis
                            WHERE cis.customer_insight_id =
                                      NEW.resulting_target_id
                              AND cis.signal_id =
                                      (ref->>'signal_id')::uuid
                              AND cis.relation = ref->>'relation'
                        )
                    ) THEN
                        RAISE EXCEPTION 'learning_application_truth_links_missing';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM customer_insight_need_links AS cinl
                        WHERE cinl.customer_insight_id =
                                  NEW.resulting_target_id
                          AND cinl.need_hypothesis_id =
                                (candidate_scope->>'need_hypothesis_id')::uuid
                          AND cinl.relation =
                                candidate_proposal->>'need_relation'
                    ) THEN
                        RAISE EXCEPTION 'learning_application_need_link_missing';
                    END IF;
                END IF;
            END IF;
            IF length(btrim(NEW.applied_by)) = 0 THEN
                RAISE EXCEPTION 'learning_application_actor_required';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_applications_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_applications
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_application()
        """
    )


def upgrade() -> None:
    op.create_table(
        "learning_candidate_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("candidate_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("target_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision in "
            "('APPROVE','REJECT','REQUEST_MORE_EVIDENCE','NO_MAP_CHANGE')",
            name="ck_learning_candidate_reviews_decision",
        ),
        sa.CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_candidate_reviews_version",
        ),
        sa.CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_candidate_reviews_snapshot_hash",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_candidate_id",
            name="uq_learning_candidate_review_candidate",
        ),
    )
    op.create_index(
        "ix_learning_candidate_reviews_project_time",
        "learning_candidate_reviews",
        ["project_id", "reviewed_at"],
        unique=False,
    )

    op.create_table(
        "learning_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_target_id", sa.Uuid(), nullable=True),
        sa.Column("applied_action", sa.String(length=32), nullable=False),
        sa.Column("applied_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("frozen_scope_json", sa.JSON(), nullable=False),
        sa.Column("before_state_hash", sa.String(length=64), nullable=True),
        sa.Column("after_state_hash", sa.String(length=64), nullable=True),
        sa.Column("customer_map_snapshot_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("change_report_json", sa.JSON(), nullable=True),
        sa.Column("applied_by", sa.String(length=200), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_applications_version",
        ),
        sa.CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_applications_snapshot_hash",
        ),
        sa.CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_applications_target_type",
        ),
        sa.CheckConstraint(
            "applied_action in "
            "('link_need_signals','link_insight_signals',"
            "'create_candidate_insight','no_map_change')",
            name="ck_learning_applications_action",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["learning_candidate_reviews.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_map_snapshot_artifact_id"],
            ["artifacts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id",
            name="uq_learning_application_review",
        ),
    )
    op.create_index(
        "ix_learning_applications_candidate",
        "learning_applications",
        ["learning_candidate_id", "candidate_version"],
        unique=False,
    )
    op.create_index(
        "ix_learning_applications_project_time",
        "learning_applications",
        ["project_id", "applied_at"],
        unique=False,
    )

    _create_guards()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS learning_applications_guard "
        "ON learning_applications"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_application()")
    op.execute(
        "DROP TRIGGER IF EXISTS learning_candidate_reviews_guard "
        "ON learning_candidate_reviews"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_candidate_review()")
    op.execute(
        "DROP TRIGGER IF EXISTS ll01c_customer_insight_project_lock "
        "ON customer_insights"
    )
    op.execute("DROP FUNCTION IF EXISTS serialize_customer_insight_project()")
    op.execute(
        "DROP FUNCTION IF EXISTS learning_candidate_applied_signal_refs(uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS learning_candidate_snapshot_hash(uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS learning_candidate_target_snapshot(uuid)"
    )

    op.drop_index(
        "ix_learning_applications_project_time",
        table_name="learning_applications",
    )
    op.drop_index(
        "ix_learning_applications_candidate",
        table_name="learning_applications",
    )
    op.drop_table("learning_applications")

    op.drop_index(
        "ix_learning_candidate_reviews_project_time",
        table_name="learning_candidate_reviews",
    )
    op.drop_table("learning_candidate_reviews")
