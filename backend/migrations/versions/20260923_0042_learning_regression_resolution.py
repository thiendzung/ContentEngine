"""Add LL-01D validation and reviewed rollback receipts.

Revision ID: 20260923_0042
Revises: 20260922_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0042"
down_revision: str | None = "20260922_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION learning_application_current_target_snapshot(
            p_application_id uuid
        ) RETURNS jsonb AS $$
        DECLARE
            app learning_applications%ROWTYPE;
            need need_hypotheses%ROWTYPE;
            insight customer_insights%ROWTYPE;
            latest_version integer;
        BEGIN
            SELECT * INTO app
            FROM learning_applications
            WHERE id = p_application_id;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'learning_validation_application_not_found';
            END IF;

            IF app.target_type = 'no_map_change' THEN
                IF app.resulting_target_id IS NOT NULL THEN
                    RAISE EXCEPTION 'learning_validation_no_map_target_invalid';
                END IF;
                RETURN jsonb_build_object(
                    'target_type', app.target_type,
                    'current_target', NULL
                );
            ELSIF app.target_type = 'need_hypothesis' THEN
                SELECT * INTO need
                FROM need_hypotheses
                WHERE id = app.resulting_target_id;

                IF NOT FOUND OR need.project_id IS DISTINCT FROM app.project_id THEN
                    RAISE EXCEPTION 'learning_validation_need_target_stale';
                END IF;

                RETURN jsonb_build_object(
                    'target_type', app.target_type,
                    'current_target', jsonb_build_object(
                        'id', need.id::text,
                        'version', need.version,
                        'status', need.status,
                        'audience_hypothesis_id',
                            CASE
                                WHEN need.audience_hypothesis_id IS NULL THEN NULL
                                ELSE need.audience_hypothesis_id::text
                            END
                    )
                );
            ELSIF app.target_type IN ('customer_insight','new_customer_insight') THEN
                SELECT * INTO insight
                FROM customer_insights
                WHERE id = app.resulting_target_id;

                IF NOT FOUND OR insight.project_id IS DISTINCT FROM app.project_id THEN
                    RAISE EXCEPTION 'learning_validation_insight_target_stale';
                END IF;

                SELECT max(ci.version)
                INTO latest_version
                FROM customer_insights AS ci
                WHERE ci.project_id = insight.project_id
                  AND ci.insight_key = insight.insight_key;

                IF latest_version IS DISTINCT FROM insight.version THEN
                    RAISE EXCEPTION 'learning_validation_insight_version_stale';
                END IF;

                RETURN jsonb_build_object(
                    'target_type', app.target_type,
                    'current_target', jsonb_build_object(
                        'id', insight.id::text,
                        'insight_key', insight.insight_key,
                        'version', insight.version,
                        'status', insight.status,
                        'audience_hypothesis_id',
                            CASE
                                WHEN insight.audience_hypothesis_id IS NULL THEN NULL
                                ELSE insight.audience_hypothesis_id::text
                            END
                    )
                );
            END IF;

            RAISE EXCEPTION 'learning_validation_target_type_invalid';
        END;
        $$ LANGUAGE plpgsql STABLE
        """
    )

    op.execute(
        """
        CREATE FUNCTION learning_validation_snapshot_hash(
            p_validation_id uuid
        ) RETURNS text AS $$
        DECLARE
            payload jsonb;
        BEGIN
            SELECT jsonb_build_object(
                'id', v.id::text,
                'project_id', v.project_id::text,
                'learning_application_id', v.learning_application_id::text,
                'learning_candidate_id', v.learning_candidate_id::text,
                'candidate_version', v.candidate_version,
                'version', v.version,
                'validation_fingerprint', v.validation_fingerprint,
                'validation_status', v.validation_status,
                'target_type', v.target_type,
                'resulting_target_id',
                    CASE
                        WHEN v.resulting_target_id IS NULL THEN NULL
                        ELSE v.resulting_target_id::text
                    END,
                'target_snapshot', v.target_snapshot_json::jsonb,
                'baseline_signal_refs', v.baseline_signal_refs_json::jsonb,
                'validation_signal_refs', v.validation_signal_refs_json::jsonb,
                'independent_evidence_groups',
                    v.independent_evidence_groups_json::jsonb,
                'metric_comparisons', v.metric_comparisons_json::jsonb,
                'frozen_scope', v.frozen_scope_json::jsonb,
                'alternative_explanations',
                    v.alternative_explanations_json::jsonb,
                'missing_evidence', v.missing_evidence_json::jsonb
            )
            INTO payload
            FROM learning_validations AS v
            WHERE v.id = p_validation_id;

            IF payload IS NULL THEN
                RAISE EXCEPTION 'learning_validation_not_found';
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
        CREATE FUNCTION validate_learning_validation()
        RETURNS trigger AS $$
        DECLARE
            app_project uuid;
            app_candidate uuid;
            app_candidate_version integer;
            app_target_type text;
            app_resulting_target uuid;
            app_scope jsonb;
            app_signal_refs jsonb;
            candidate_status text;
            locked_candidate_key text;
            latest_candidate_version integer;
            expected_version integer;
            signal_ref jsonb;
            signal_project uuid;
            signal_fingerprint text;
            signal_group text;
            expected_groups jsonb;
            baseline_groups text[];
            comparison jsonb;
            baseline_metric performance_metrics%ROWTYPE;
            candidate_metric performance_metrics%ROWTYPE;
            expected_delta numeric;
            expected_direction text;
            new_support_groups integer;
            new_contradict_groups integer;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_validation_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_validation_delete_forbidden';
            END IF;

            SELECT project_id, learning_candidate_id, candidate_version,
                   target_type, resulting_target_id, frozen_scope_json::jsonb,
                   applied_signal_refs_json::jsonb
            INTO app_project, app_candidate, app_candidate_version,
                 app_target_type, app_resulting_target, app_scope,
                 app_signal_refs
            FROM learning_applications
            WHERE id = NEW.learning_application_id;

            IF app_project IS NULL
               OR NEW.project_id IS DISTINCT FROM app_project
               OR NEW.learning_candidate_id IS DISTINCT FROM app_candidate
               OR NEW.candidate_version IS DISTINCT FROM app_candidate_version
               OR NEW.target_type IS DISTINCT FROM app_target_type
               OR NEW.resulting_target_id IS DISTINCT FROM app_resulting_target
               OR NEW.frozen_scope_json::jsonb IS DISTINCT FROM app_scope
               OR NEW.target_snapshot_json::jsonb IS DISTINCT FROM
                    learning_application_current_target_snapshot(
                        NEW.learning_application_id
                    ) THEN
                RAISE EXCEPTION 'learning_validation_identity_mismatch';
            END IF;

            PERFORM 1
            FROM projects
            WHERE id = NEW.project_id
            FOR UPDATE;

            SELECT status, candidate_key
            INTO candidate_status, locked_candidate_key
            FROM learning_candidates
            WHERE id = NEW.learning_candidate_id;

            SELECT max(version)
            INTO latest_candidate_version
            FROM learning_candidates
            WHERE project_id = NEW.project_id
              AND learning_candidates.candidate_key = locked_candidate_key;

            IF candidate_status IS DISTINCT FROM 'OPEN'
               OR latest_candidate_version IS DISTINCT FROM NEW.candidate_version THEN
                RAISE EXCEPTION 'learning_validation_candidate_stale';
            END IF;

            SELECT coalesce(max(v.version), 0) + 1
            INTO expected_version
            FROM learning_validations AS v
            WHERE v.learning_application_id = NEW.learning_application_id;

            IF NEW.version IS DISTINCT FROM expected_version THEN
                RAISE EXCEPTION 'learning_validation_version_invalid';
            END IF;

            IF jsonb_array_length(NEW.validation_signal_refs_json::jsonb) = 0
               AND NEW.validation_status IN ('VALIDATED','REGRESSED','CONTESTED') THEN
                RAISE EXCEPTION 'learning_validation_evidence_required';
            END IF;

            IF jsonb_array_length(NEW.baseline_signal_refs_json::jsonb)
               IS DISTINCT FROM jsonb_array_length(app_signal_refs)
               OR jsonb_array_length(NEW.baseline_signal_refs_json::jsonb)
               IS DISTINCT FROM (
                   SELECT count(DISTINCT baseline_ref->>'signal_id')
                   FROM jsonb_array_elements(
                       NEW.baseline_signal_refs_json::jsonb
                   ) AS baseline_ref
               ) THEN
                RAISE EXCEPTION 'learning_validation_baseline_signal_mismatch';
            END IF;

            FOR signal_ref IN
                SELECT value
                FROM jsonb_array_elements(
                    NEW.baseline_signal_refs_json::jsonb
                )
            LOOP
                IF signal_ref->>'relation' NOT IN
                   ('supports','contradicts','context')
                   OR NOT EXISTS (
                       SELECT 1
                       FROM jsonb_array_elements(app_signal_refs) AS app_ref
                       WHERE app_ref->>'signal_id'
                             = signal_ref->>'signal_id'
                         AND app_ref->>'relation'
                             = signal_ref->>'relation'
                   ) THEN
                    RAISE EXCEPTION
                        'learning_validation_baseline_signal_mismatch';
                END IF;

                SELECT project_id, fingerprint, independence_group
                INTO signal_project, signal_fingerprint, signal_group
                FROM signals
                WHERE id = (signal_ref->>'signal_id')::uuid
                  AND source_kind = 'MOTGU'
                  AND scope = 'motgu_site';

                IF signal_project IS NULL
                   OR signal_project IS DISTINCT FROM NEW.project_id
                   OR signal_ref->>'fingerprint'
                        IS DISTINCT FROM signal_fingerprint
                   OR signal_ref->>'independence_key'
                        IS DISTINCT FROM signal_group THEN
                    RAISE EXCEPTION
                        'learning_validation_baseline_signal_mismatch';
                END IF;
            END LOOP;

            FOR signal_ref IN
                SELECT value
                FROM jsonb_array_elements(
                    NEW.validation_signal_refs_json::jsonb
                )
            LOOP
                IF signal_ref->>'relation' NOT IN
                   ('supports','contradicts','context') THEN
                    RAISE EXCEPTION 'learning_validation_signal_relation_invalid';
                END IF;

                SELECT project_id, fingerprint, independence_group
                INTO signal_project, signal_fingerprint, signal_group
                FROM signals
                WHERE id = (signal_ref->>'signal_id')::uuid
                  AND source_kind = 'MOTGU'
                  AND scope = 'motgu_site';

                IF signal_project IS NULL
                   OR signal_project IS DISTINCT FROM NEW.project_id
                   OR signal_ref->>'fingerprint'
                        IS DISTINCT FROM signal_fingerprint
                   OR signal_ref->>'independence_key'
                        IS DISTINCT FROM signal_group THEN
                    RAISE EXCEPTION 'learning_validation_signal_project_mismatch';
                END IF;
            END LOOP;

            SELECT array_agg(DISTINCT s.independence_group)
            INTO baseline_groups
            FROM jsonb_array_elements(
                NEW.baseline_signal_refs_json::jsonb
            ) AS baseline_ref
            JOIN signals AS s
              ON s.id = (baseline_ref->>'signal_id')::uuid;

            SELECT COALESCE(
                jsonb_agg(group_key ORDER BY group_key),
                '[]'::jsonb
            )
            INTO expected_groups
            FROM (
                SELECT DISTINCT
                    validation_ref->>'independence_key' AS group_key
                FROM jsonb_array_elements(
                    NEW.validation_signal_refs_json::jsonb
                ) AS validation_ref
                WHERE validation_ref->>'relation' IN ('supports','contradicts')
                  AND NOT (
                      validation_ref->>'independence_key'
                      = ANY(COALESCE(baseline_groups, ARRAY[]::text[]))
                  )
            ) AS groups;

            IF NEW.independent_evidence_groups_json::jsonb
                 IS DISTINCT FROM expected_groups THEN
                RAISE EXCEPTION 'learning_validation_independence_mismatch';
            END IF;

            SELECT
                count(DISTINCT validation_ref->>'independence_key')
                    FILTER (
                        WHERE validation_ref->>'relation' = 'supports'
                          AND NOT (
                              validation_ref->>'independence_key'
                              = ANY(COALESCE(baseline_groups, ARRAY[]::text[]))
                          )
                    ),
                count(DISTINCT validation_ref->>'independence_key')
                    FILTER (
                        WHERE validation_ref->>'relation' = 'contradicts'
                          AND NOT (
                              validation_ref->>'independence_key'
                              = ANY(COALESCE(baseline_groups, ARRAY[]::text[]))
                          )
                    )
            INTO new_support_groups, new_contradict_groups
            FROM jsonb_array_elements(
                NEW.validation_signal_refs_json::jsonb
            ) AS validation_ref;

            IF NEW.validation_status = 'VALIDATED'
               AND (
                   new_support_groups < 1
                   OR new_contradict_groups > 0
               ) THEN
                RAISE EXCEPTION 'learning_validation_validated_evidence_invalid';
            ELSIF NEW.validation_status = 'REGRESSED'
               AND (
                   new_contradict_groups < 1
                   OR new_support_groups > 0
               ) THEN
                RAISE EXCEPTION 'learning_validation_regressed_evidence_invalid';
            ELSIF NEW.validation_status = 'CONTESTED'
               AND (
                   new_support_groups < 1
                   OR new_contradict_groups < 1
               ) THEN
                RAISE EXCEPTION 'learning_validation_contested_evidence_invalid';
            ELSIF NEW.validation_status = 'NEEDS_MORE_EVIDENCE'
               AND (
                   new_support_groups > 0
                   OR new_contradict_groups > 0
                   OR jsonb_array_length(NEW.missing_evidence_json::jsonb) = 0
               ) THEN
                RAISE EXCEPTION 'learning_validation_more_evidence_status_invalid';
            ELSIF NEW.validation_status = 'INCONCLUSIVE'
               AND jsonb_array_length(NEW.missing_evidence_json::jsonb) = 0 THEN
                RAISE EXCEPTION 'learning_validation_missing_evidence_required';
            END IF;

            IF jsonb_array_length(NEW.validation_signal_refs_json::jsonb)
               IS DISTINCT FROM (
                   SELECT count(DISTINCT validation_ref->>'signal_id')
                   FROM jsonb_array_elements(
                       NEW.validation_signal_refs_json::jsonb
                   ) AS validation_ref
               ) THEN
                RAISE EXCEPTION 'learning_validation_signal_duplicate';
            END IF;

            FOR comparison IN
                SELECT value
                FROM jsonb_array_elements(
                    NEW.metric_comparisons_json::jsonb
                )
            LOOP
                SELECT * INTO baseline_metric
                FROM performance_metrics
                WHERE id = (comparison->>'baseline_metric_id')::uuid;

                SELECT * INTO candidate_metric
                FROM performance_metrics
                WHERE id = (comparison->>'candidate_metric_id')::uuid;

                IF baseline_metric.id IS NULL
                   OR candidate_metric.id IS NULL
                   OR baseline_metric.metric_name
                        IS DISTINCT FROM candidate_metric.metric_name
                   OR baseline_metric.provider
                        IS DISTINCT FROM candidate_metric.provider
                   OR baseline_metric.dimensions_json::jsonb
                        IS DISTINCT FROM candidate_metric.dimensions_json::jsonb
                   OR comparison->>'metric_name'
                        IS DISTINCT FROM baseline_metric.metric_name
                   OR comparison->>'provider'
                        IS DISTINCT FROM baseline_metric.provider
                   OR comparison->>'baseline_value'
                        IS DISTINCT FROM trim(
                            trailing '.' FROM trim(
                                trailing '0' FROM baseline_metric.metric_value::text
                            )
                        )
                   OR comparison->>'candidate_value'
                        IS DISTINCT FROM trim(
                            trailing '.' FROM trim(
                                trailing '0' FROM candidate_metric.metric_value::text
                            )
                        ) THEN
                    RAISE EXCEPTION 'learning_validation_metric_mismatch';
                END IF;

                expected_delta :=
                    candidate_metric.metric_value - baseline_metric.metric_value;
                expected_direction := CASE
                    WHEN expected_delta > 0 THEN 'INCREASE'
                    WHEN expected_delta < 0 THEN 'DECREASE'
                    ELSE 'UNCHANGED'
                END;

                IF (comparison->>'delta')::numeric
                        IS DISTINCT FROM expected_delta
                   OR comparison->>'direction'
                        IS DISTINCT FROM expected_direction
                   OR comparison->>'causal_claim_allowed'
                        IS DISTINCT FROM 'false'
                   OR NOT EXISTS (
                       SELECT 1
                       FROM jsonb_array_elements(
                           NEW.baseline_signal_refs_json::jsonb
                       ) AS baseline_ref
                       JOIN signals AS s
                         ON s.id = (baseline_ref->>'signal_id')::uuid
                       CROSS JOIN LATERAL jsonb_array_elements(
                           s.provenance_json::jsonb->'metrics'
                       ) AS metric_ref
                       WHERE metric_ref->>'id'
                             = comparison->>'baseline_metric_id'
                   )
                   OR NOT EXISTS (
                       SELECT 1
                       FROM jsonb_array_elements(
                           NEW.validation_signal_refs_json::jsonb
                       ) AS validation_ref
                       JOIN signals AS s
                         ON s.id = (validation_ref->>'signal_id')::uuid
                       CROSS JOIN LATERAL jsonb_array_elements(
                           s.provenance_json::jsonb->'metrics'
                       ) AS metric_ref
                       WHERE metric_ref->>'id'
                             = comparison->>'candidate_metric_id'
                   ) THEN
                    RAISE EXCEPTION 'learning_validation_metric_mismatch';
                END IF;
            END LOOP;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_validations_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_validations
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_validation()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_learning_resolution()
        RETURNS trigger AS $$
        DECLARE
            validation_project uuid;
            validation_application uuid;
            validation_version integer;
            validation_status text;
            latest_version integer;
            expected_hash text;
            current_target jsonb;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_resolution_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_resolution_delete_forbidden';
            END IF;

            SELECT project_id, learning_application_id, version,
                   validation_status
            INTO validation_project, validation_application,
                 validation_version, validation_status
            FROM learning_validations
            WHERE id = NEW.learning_validation_id;

            IF validation_project IS NULL
               OR NEW.project_id IS DISTINCT FROM validation_project
               OR NEW.learning_application_id IS DISTINCT FROM validation_application
               OR NEW.validation_version IS DISTINCT FROM validation_version THEN
                RAISE EXCEPTION 'learning_resolution_identity_mismatch';
            END IF;

            SELECT max(v.version)
            INTO latest_version
            FROM learning_validations AS v
            WHERE v.learning_application_id = validation_application;

            IF latest_version IS DISTINCT FROM validation_version THEN
                RAISE EXCEPTION 'learning_resolution_validation_stale';
            END IF;

            expected_hash :=
                learning_validation_snapshot_hash(NEW.learning_validation_id);
            current_target :=
                learning_application_current_target_snapshot(
                    NEW.learning_application_id
                );

            IF NEW.validation_snapshot_hash IS DISTINCT FROM expected_hash
               OR NEW.target_snapshot_json::jsonb IS DISTINCT FROM current_target THEN
                RAISE EXCEPTION 'learning_resolution_snapshot_mismatch';
            END IF;

            IF length(btrim(NEW.reviewed_by)) = 0
               OR length(btrim(NEW.reason)) = 0 THEN
                RAISE EXCEPTION 'learning_resolution_human_fields_required';
            END IF;

            PERFORM 1
            FROM projects
            WHERE id = NEW.project_id
            FOR UPDATE;

            IF EXISTS (
                SELECT 1
                FROM learning_validations AS v
                JOIN learning_applications AS la
                  ON la.id = v.learning_application_id
                JOIN learning_candidates AS lc
                  ON lc.id = la.learning_candidate_id
                WHERE v.id = NEW.learning_validation_id
                  AND (
                      lc.status <> 'OPEN'
                      OR EXISTS (
                          SELECT 1
                          FROM learning_candidates AS newer
                          WHERE newer.project_id = lc.project_id
                            AND newer.candidate_key = lc.candidate_key
                            AND newer.version > lc.version
                      )
                  )
            ) THEN
                RAISE EXCEPTION 'learning_resolution_candidate_stale';
            END IF;

            IF NEW.decision IN ('PROMOTE','ROLLBACK','REJECT')
               AND EXISTS (
                   SELECT 1
                   FROM learning_validations AS v
                   WHERE v.id = NEW.learning_validation_id
                     AND v.target_type = 'no_map_change'
               ) THEN
                RAISE EXCEPTION 'learning_resolution_no_map_mutation_invalid';
            END IF;

            IF NEW.decision = 'PROMOTE' THEN
                IF validation_status IS DISTINCT FROM 'VALIDATED'
                   OR NEW.target_status NOT IN ('TESTING','SUPPORTED') THEN
                    RAISE EXCEPTION 'learning_resolution_promote_invalid';
                END IF;
            ELSIF NEW.decision IN ('ROLLBACK','REJECT') THEN
                IF validation_status IS DISTINCT FROM 'REGRESSED'
                   OR NEW.target_status NOT IN
                      ('REJECTED','INSUFFICIENT_EVIDENCE') THEN
                    RAISE EXCEPTION 'learning_resolution_rollback_invalid';
                END IF;
            ELSIF NEW.target_status IS NOT NULL THEN
                RAISE EXCEPTION 'learning_resolution_target_status_unexpected';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_resolutions_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_resolutions
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_resolution()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_learning_resolution_application()
        RETURNS trigger AS $$
        DECLARE
            resolution_project uuid;
            resolution_validation uuid;
            resolution_application uuid;
            resolution_decision text;
            resolution_status text;
            resolution_reviewer text;
            resolution_reason text;
            validation_target_type text;
            validation_target_id uuid;
            map_project uuid;
            map_hash text;
            map_type text;
            map_run_id uuid;
            candidate_id uuid;
            candidate_status text;
            resolution_target_snapshot jsonb;
            current_target_snapshot jsonb;
            validation_ref jsonb;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_resolution_application_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_resolution_application_delete_forbidden';
            END IF;

            PERFORM 1
            FROM projects
            WHERE id = NEW.project_id
            FOR UPDATE;

            SELECT project_id, learning_validation_id,
                   learning_application_id, decision, target_status,
                   reviewed_by, reason, target_snapshot_json::jsonb
            INTO resolution_project, resolution_validation,
                 resolution_application, resolution_decision,
                 resolution_status, resolution_reviewer, resolution_reason,
                 resolution_target_snapshot
            FROM learning_resolutions
            WHERE id = NEW.learning_resolution_id;

            SELECT target_type, resulting_target_id
            INTO validation_target_type, validation_target_id
            FROM learning_validations
            WHERE id = resolution_validation;

            IF resolution_project IS NULL
               OR NEW.project_id IS DISTINCT FROM resolution_project
               OR NEW.learning_validation_id IS DISTINCT FROM resolution_validation
               OR NEW.learning_application_id IS DISTINCT FROM resolution_application
               OR NEW.decision IS DISTINCT FROM resolution_decision
               OR NEW.target_type IS DISTINCT FROM validation_target_type
               OR NEW.resulting_target_id IS DISTINCT FROM validation_target_id
               OR NEW.before_target_snapshot_json::jsonb
                    IS DISTINCT FROM resolution_target_snapshot THEN
                RAISE EXCEPTION 'learning_resolution_application_identity_mismatch';
            END IF;

            current_target_snapshot :=
                learning_application_current_target_snapshot(
                    NEW.learning_application_id
                );

            IF resolution_decision IN ('KEEP','REQUEST_MORE_EVIDENCE') THEN
                IF NEW.applied_action IS DISTINCT FROM 'no_map_change'
                   OR NEW.resulting_status IS NOT NULL
                   OR NEW.before_state_hash IS NOT NULL
                   OR NEW.after_state_hash IS NOT NULL
                   OR NEW.customer_map_snapshot_artifact_id IS NOT NULL
                   OR NEW.change_report_json IS NOT NULL
                   OR NEW.after_target_snapshot_json::jsonb
                        IS DISTINCT FROM resolution_target_snapshot
                   OR current_target_snapshot
                        IS DISTINCT FROM resolution_target_snapshot THEN
                    RAISE EXCEPTION 'learning_resolution_application_noop_invalid';
                END IF;
                RETURN NEW;
            END IF;

            IF resolution_decision = 'ARCHIVE_CANDIDATE' THEN
                SELECT lc.id, lc.status
                INTO candidate_id, candidate_status
                FROM learning_applications AS la
                JOIN learning_candidates AS lc
                  ON lc.id = la.learning_candidate_id
                WHERE la.id = NEW.learning_application_id;

                IF candidate_id IS NULL
                   OR candidate_status IS DISTINCT FROM 'ARCHIVED'
                   OR NEW.applied_action IS DISTINCT FROM 'archive_candidate'
                   OR NEW.resulting_status IS DISTINCT FROM 'ARCHIVED'
                   OR NEW.before_state_hash IS NOT NULL
                   OR NEW.after_state_hash IS NOT NULL
                   OR NEW.customer_map_snapshot_artifact_id IS NOT NULL
                   OR NEW.change_report_json IS NOT NULL
                   OR NEW.after_target_snapshot_json::jsonb
                        IS DISTINCT FROM resolution_target_snapshot
                   OR current_target_snapshot
                        IS DISTINCT FROM resolution_target_snapshot THEN
                    RAISE EXCEPTION 'learning_resolution_application_archive_invalid';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.resulting_status IS DISTINCT FROM resolution_status
               OR NEW.before_state_hash IS NULL
               OR NEW.after_state_hash IS NULL
               OR NEW.customer_map_snapshot_artifact_id IS NULL
               OR NEW.change_report_json IS NULL
               OR NEW.after_target_snapshot_json::jsonb
                    IS DISTINCT FROM current_target_snapshot THEN
                RAISE EXCEPTION 'learning_resolution_application_receipt_incomplete';
            END IF;

            SELECT run.project_id, artifact.content_hash,
                   artifact.artifact_type, artifact.run_id
            INTO map_project, map_hash, map_type, map_run_id
            FROM artifacts AS artifact
            JOIN content_runs AS run ON run.id = artifact.run_id
            WHERE artifact.id = NEW.customer_map_snapshot_artifact_id;

            IF map_project IS DISTINCT FROM NEW.project_id
               OR map_type IS DISTINCT FROM 'customer_map_snapshot'
               OR map_hash IS DISTINCT FROM NEW.after_state_hash
               OR NEW.change_report_json->>'current_snapshot_hash'
                    IS DISTINCT FROM NEW.after_state_hash
               OR NEW.change_report_json->>'previous_snapshot_hash'
                    IS DISTINCT FROM NEW.before_state_hash
               OR NOT EXISTS (
                   SELECT 1
                   FROM artifacts AS prior_artifact
                   WHERE prior_artifact.run_id = map_run_id
                     AND prior_artifact.artifact_type = 'customer_map_snapshot'
                     AND prior_artifact.content_hash = NEW.before_state_hash
               ) THEN
                RAISE EXCEPTION 'learning_resolution_application_map_mismatch';
            END IF;

            IF length(btrim(NEW.applied_by)) = 0 THEN
                RAISE EXCEPTION 'learning_resolution_application_actor_required';
            END IF;

            IF NEW.target_type = 'need_hypothesis' THEN
                IF NEW.applied_action IS DISTINCT FROM 'review_need'
                   OR NOT EXISTS (
                       SELECT 1
                       FROM need_hypotheses AS nh
                       WHERE nh.id = NEW.resulting_target_id
                         AND nh.project_id = NEW.project_id
                         AND nh.status = resolution_status
                   )
                   OR NOT EXISTS (
                       SELECT 1
                       FROM need_hypothesis_reviews AS nhr
                       JOIN need_hypotheses AS nh
                         ON nh.id = nhr.need_hypothesis_id
                       WHERE nhr.need_hypothesis_id = NEW.resulting_target_id
                         AND nhr.version = nh.version - 1
                         AND nhr.status = resolution_status
                         AND nhr.reviewed_by = resolution_reviewer
                         AND nhr.reason = resolution_reason
                   ) THEN
                    RAISE EXCEPTION 'learning_resolution_application_need_review_missing';
                END IF;

                FOR validation_ref IN
                    SELECT value
                    FROM learning_validations AS lv,
                         LATERAL jsonb_array_elements(
                             lv.validation_signal_refs_json::jsonb
                         )
                    WHERE lv.id = NEW.learning_validation_id
                      AND value->>'relation' IN ('supports','contradicts')
                LOOP
                    IF NOT EXISTS (
                        SELECT 1
                        FROM need_hypothesis_signals AS nhs
                        WHERE nhs.need_hypothesis_id = NEW.resulting_target_id
                          AND nhs.signal_id =
                              (validation_ref->>'signal_id')::uuid
                          AND nhs.relation = validation_ref->>'relation'
                    )
                       OR EXISTS (
                        SELECT 1
                        FROM need_hypothesis_signals AS nhs
                        WHERE nhs.need_hypothesis_id = NEW.resulting_target_id
                          AND nhs.signal_id =
                              (validation_ref->>'signal_id')::uuid
                          AND nhs.relation <> validation_ref->>'relation'
                    ) THEN
                        RAISE EXCEPTION
                            'learning_resolution_application_need_evidence_missing';
                    END IF;
                END LOOP;
            ELSIF NEW.target_type IN ('customer_insight','new_customer_insight') THEN
                IF NEW.applied_action IS DISTINCT FROM 'review_insight'
                   OR NOT EXISTS (
                       SELECT 1
                       FROM customer_insights AS ci
                       WHERE ci.id = NEW.resulting_target_id
                         AND ci.project_id = NEW.project_id
                         AND ci.status = resolution_status
                   )
                   OR NOT EXISTS (
                       SELECT 1
                       FROM customer_insight_reviews AS cir
                       JOIN customer_insights AS ci
                         ON ci.id = cir.customer_insight_id
                       WHERE cir.customer_insight_id = NEW.resulting_target_id
                         AND cir.status = resolution_status
                         AND cir.reviewed_by = resolution_reviewer
                         AND cir.reason = resolution_reason
                         AND ci.reviewed_by = resolution_reviewer
                         AND ci.review_reason = resolution_reason
                         AND ci.reviewed_at = cir.reviewed_at
                   ) THEN
                    RAISE EXCEPTION 'learning_resolution_application_insight_review_missing';
                END IF;

                FOR validation_ref IN
                    SELECT value
                    FROM learning_validations AS lv,
                         LATERAL jsonb_array_elements(
                             lv.validation_signal_refs_json::jsonb
                         )
                    WHERE lv.id = NEW.learning_validation_id
                LOOP
                    IF NOT EXISTS (
                        SELECT 1
                        FROM customer_insight_signals AS cis
                        WHERE cis.customer_insight_id = NEW.resulting_target_id
                          AND cis.signal_id =
                              (validation_ref->>'signal_id')::uuid
                          AND cis.relation = validation_ref->>'relation'
                    ) THEN
                        RAISE EXCEPTION
                            'learning_resolution_application_insight_evidence_missing';
                    END IF;
                END LOOP;
            ELSE
                RAISE EXCEPTION 'learning_resolution_application_target_invalid';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_resolution_applications_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_resolution_applications
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_resolution_application()
        """
    )


def upgrade() -> None:
    op.create_table(
        "learning_validations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_application_id",
            sa.Uuid(),
            sa.ForeignKey("learning_applications.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_candidate_id",
            sa.Uuid(),
            sa.ForeignKey("learning_candidates.id"),
            nullable=False,
        ),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("validation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("resulting_target_id", sa.Uuid()),
        sa.Column("target_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("baseline_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("validation_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column(
            "independent_evidence_groups_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("metric_comparisons_json", sa.JSON(), nullable=False),
        sa.Column("frozen_scope_json", sa.JSON(), nullable=False),
        sa.Column(
            "alternative_explanations_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("missing_evidence_json", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_version > 0 and version > 0",
            name="ck_learning_validations_versions",
        ),
        sa.CheckConstraint(
            "validation_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_learning_validations_fingerprint",
        ),
        sa.CheckConstraint(
            "validation_status in "
            "('NEEDS_MORE_EVIDENCE','INCONCLUSIVE','VALIDATED','REGRESSED','CONTESTED')",
            name="ck_learning_validations_status",
        ),
        sa.CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_validations_target_type",
        ),
        sa.UniqueConstraint(
            "learning_application_id",
            "version",
            name="uq_learning_validation_application_version",
        ),
        sa.UniqueConstraint(
            "learning_application_id",
            "validation_fingerprint",
            name="uq_learning_validation_application_fingerprint",
        ),
    )
    op.create_index(
        "ix_learning_validations_project_time",
        "learning_validations",
        ["project_id", "evaluated_at"],
    )

    op.create_table(
        "learning_resolutions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_validation_id",
            sa.Uuid(),
            sa.ForeignKey("learning_validations.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_application_id",
            sa.Uuid(),
            sa.ForeignKey("learning_applications.id"),
            nullable=False,
        ),
        sa.Column("validation_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("target_status", sa.String(length=32)),
        sa.Column("reviewed_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "validation_snapshot_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("target_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "validation_version > 0",
            name="ck_learning_resolutions_version",
        ),
        sa.CheckConstraint(
            "decision in "
            "('PROMOTE','KEEP','ROLLBACK','REJECT','REQUEST_MORE_EVIDENCE','ARCHIVE_CANDIDATE')",
            name="ck_learning_resolutions_decision",
        ),
        sa.CheckConstraint(
            "validation_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_resolutions_snapshot_hash",
        ),
        sa.UniqueConstraint(
            "learning_validation_id",
            name="uq_learning_resolution_validation",
        ),
    )
    op.create_index(
        "ix_learning_resolutions_project_time",
        "learning_resolutions",
        ["project_id", "reviewed_at"],
    )

    op.create_table(
        "learning_resolution_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_resolution_id",
            sa.Uuid(),
            sa.ForeignKey("learning_resolutions.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_validation_id",
            sa.Uuid(),
            sa.ForeignKey("learning_validations.id"),
            nullable=False,
        ),
        sa.Column(
            "learning_application_id",
            sa.Uuid(),
            sa.ForeignKey("learning_applications.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("resulting_target_id", sa.Uuid()),
        sa.Column("resulting_status", sa.String(length=32)),
        sa.Column("applied_action", sa.String(length=32), nullable=False),
        sa.Column("before_target_snapshot_json", sa.JSON()),
        sa.Column("after_target_snapshot_json", sa.JSON()),
        sa.Column("before_state_hash", sa.String(length=64)),
        sa.Column("after_state_hash", sa.String(length=64)),
        sa.Column(
            "customer_map_snapshot_artifact_id",
            sa.Uuid(),
            sa.ForeignKey("artifacts.id"),
        ),
        sa.Column("change_report_json", sa.JSON()),
        sa.Column("applied_by", sa.String(length=200), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision in "
            "('PROMOTE','KEEP','ROLLBACK','REJECT','REQUEST_MORE_EVIDENCE','ARCHIVE_CANDIDATE')",
            name="ck_learning_resolution_applications_decision",
        ),
        sa.CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_resolution_applications_target_type",
        ),
        sa.CheckConstraint(
            "applied_action in "
            "('review_need','review_insight','archive_candidate','no_map_change')",
            name="ck_learning_resolution_applications_action",
        ),
        sa.UniqueConstraint(
            "learning_resolution_id",
            name="uq_learning_resolution_application_resolution",
        ),
    )
    op.create_index(
        "ix_learning_resolution_applications_project_time",
        "learning_resolution_applications",
        ["project_id", "applied_at"],
    )

    _create_guards()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS learning_resolution_applications_guard "
        "ON learning_resolution_applications"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS validate_learning_resolution_application()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS learning_resolutions_guard "
        "ON learning_resolutions"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_resolution()")
    op.execute(
        "DROP TRIGGER IF EXISTS learning_validations_guard "
        "ON learning_validations"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_validation()")
    op.execute(
        "DROP FUNCTION IF EXISTS learning_validation_snapshot_hash(uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS learning_application_current_target_snapshot(uuid)"
    )

    op.drop_index(
        "ix_learning_resolution_applications_project_time",
        table_name="learning_resolution_applications",
    )
    op.drop_table("learning_resolution_applications")
    op.drop_index(
        "ix_learning_resolutions_project_time",
        table_name="learning_resolutions",
    )
    op.drop_table("learning_resolutions")
    op.drop_index(
        "ix_learning_validations_project_time",
        table_name="learning_validations",
    )
    op.drop_table("learning_validations")
