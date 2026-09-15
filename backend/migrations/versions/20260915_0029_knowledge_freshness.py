"""Add time-aware knowledge freshness policy and verification records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0029"
down_revision: str | None = "20260915_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_freshness_guards() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_source_document_observation() RETURNS trigger AS $$
            DECLARE
                stored_hash text;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'source_document_observation_is_immutable';
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'source_document_observation_is_immutable';
                END IF;
                SELECT content_hash INTO stored_hash
                FROM source_documents WHERE id = NEW.source_document_id;
                IF stored_hash IS DISTINCT FROM NEW.content_hash THEN
                    RAISE EXCEPTION 'source_document_observation_hash_mismatch';
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
            CREATE TRIGGER source_document_observations_guard
            BEFORE INSERT OR UPDATE OR DELETE ON source_document_observations
            FOR EACH ROW EXECUTE FUNCTION validate_source_document_observation()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION enforce_freshness_policy_lifecycle() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'freshness_policy_is_immutable';
                END IF;
                IF TG_OP = 'INSERT' THEN
                    IF NEW.status <> 'active' THEN
                        RAISE EXCEPTION 'freshness_policy_must_start_active';
                    END IF;
                    RETURN NEW;
                END IF;
                IF OLD.status = 'retired' THEN
                    RAISE EXCEPTION 'retired_freshness_policy_is_immutable';
                END IF;
                IF NEW.status <> 'retired'
                    OR NEW.project_id IS DISTINCT FROM OLD.project_id
                    OR NEW.policy_key IS DISTINCT FROM OLD.policy_key
                    OR NEW.version IS DISTINCT FROM OLD.version
                    OR NEW.freshness_class IS DISTINCT FROM OLD.freshness_class
                    OR NEW.max_age_days IS DISTINCT FROM OLD.max_age_days
                    OR NEW.refresh_lead_days IS DISTINCT FROM OLD.refresh_lead_days
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
                    OR NEW.rationale IS DISTINCT FROM OLD.rationale
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                    RAISE EXCEPTION 'freshness_policy_is_immutable';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM freshness_assignments
                    WHERE policy_id = OLD.id AND status = 'active'
                ) THEN
                    RAISE EXCEPTION 'freshness_policy_has_active_assignments';
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
            CREATE TRIGGER freshness_policies_lifecycle_guard
            BEFORE INSERT OR UPDATE OR DELETE ON freshness_policies
            FOR EACH ROW EXECUTE FUNCTION enforce_freshness_policy_lifecycle()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_freshness_assignment() RETURNS trigger AS $$
            DECLARE
                policy_project uuid;
                policy_status text;
                target_project uuid;
                topic_status text;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'freshness_assignment_is_immutable';
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    IF OLD.status <> 'active' OR NEW.status <> 'retired'
                        OR NEW.project_id IS DISTINCT FROM OLD.project_id
                        OR NEW.policy_id IS DISTINCT FROM OLD.policy_id
                        OR NEW.topic_id IS DISTINCT FROM OLD.topic_id
                        OR NEW.claim_id IS DISTINCT FROM OLD.claim_id
                        OR NEW.knowledge_candidate_id IS DISTINCT FROM OLD.knowledge_candidate_id
                        OR NEW.assigned_by IS DISTINCT FROM OLD.assigned_by
                        OR NEW.reason IS DISTINCT FROM OLD.reason
                        OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id
                        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                        RAISE EXCEPTION 'freshness_assignment_is_immutable';
                    END IF;
                    RETURN NEW;
                END IF;

                IF NEW.status <> 'active' THEN
                    RAISE EXCEPTION 'freshness_assignment_must_start_active';
                END IF;
                SELECT project_id, status INTO policy_project, policy_status
                FROM freshness_policies WHERE id = NEW.policy_id;
                IF policy_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'freshness_assignment_policy_project_mismatch';
                END IF;
                IF policy_status <> 'active' THEN
                    RAISE EXCEPTION 'freshness_assignment_policy_not_active';
                END IF;

                IF NEW.topic_id IS NOT NULL THEN
                    SELECT project_id, status INTO target_project, topic_status
                    FROM topic_nodes WHERE id = NEW.topic_id;
                    IF topic_status <> 'active' THEN
                        RAISE EXCEPTION 'freshness_assignment_topic_not_active';
                    END IF;
                ELSIF NEW.claim_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM claims WHERE id = NEW.claim_id;
                ELSIF NEW.knowledge_candidate_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM knowledge_candidates
                    WHERE id = NEW.knowledge_candidate_id AND status = 'APPROVED';
                END IF;
                IF target_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'freshness_assignment_target_project_mismatch';
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
            CREATE TRIGGER freshness_assignments_guard
            BEFORE INSERT OR UPDATE OR DELETE ON freshness_assignments
            FOR EACH ROW EXECUTE FUNCTION validate_freshness_assignment()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_freshness_verification() RETURNS trigger AS $$
            DECLARE
                target_project uuid;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'freshness_verification_is_immutable';
                END IF;
                IF NEW.claim_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM claims WHERE id = NEW.claim_id;
                ELSIF NEW.knowledge_candidate_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM knowledge_candidates
                    WHERE id = NEW.knowledge_candidate_id AND status = 'APPROVED';
                END IF;
                IF target_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'freshness_verification_target_project_mismatch';
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
            CREATE TRIGGER freshness_verifications_guard
            BEFORE INSERT OR UPDATE OR DELETE ON freshness_verifications
            FOR EACH ROW EXECUTE FUNCTION validate_freshness_verification()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "source_document_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("reader", sa.String(length=64), nullable=True),
        sa.Column("observation_method", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_source_document_observations_hash",
        ),
        sa.CheckConstraint(
            "observation_method in ('document_ingest','migration_backfill')",
            name="ck_source_document_observations_method",
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "observed_at",
            "observation_method",
            name="uq_source_document_observation_event",
        ),
    )
    op.create_index(
        "ix_source_document_observations_document_time",
        "source_document_observations",
        ["source_document_id", "observed_at"],
        unique=False,
    )

    op.create_table(
        "freshness_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("policy_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("freshness_class", sa.String(length=16), nullable=False),
        sa.Column("max_age_days", sa.Integer(), nullable=False),
        sa.Column("refresh_lead_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by", sa.String(length=200), nullable=True),
        sa.Column("retirement_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "freshness_class in ('evergreen','slow','medium','fast')",
            name="ck_freshness_policies_class",
        ),
        sa.CheckConstraint(
            "max_age_days >= 1 and max_age_days <= 3650",
            name="ck_freshness_policies_max_age",
        ),
        sa.CheckConstraint(
            "refresh_lead_days >= 0 and refresh_lead_days < max_age_days",
            name="ck_freshness_policies_refresh_lead",
        ),
        sa.CheckConstraint(
            "status in ('active','retired')",
            name="ck_freshness_policies_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_freshness_policies_version"),
        sa.CheckConstraint(
            "(status = 'active' AND retired_at IS NULL AND retired_by IS NULL "
            "AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL "
            "AND retired_by IS NOT NULL AND btrim(retired_by) <> '' "
            "AND retirement_reason IS NOT NULL AND btrim(retirement_reason) <> '')",
            name="ck_freshness_policies_retirement_audit",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_freshness_policy_version",
        "freshness_policies",
        ["project_id", "policy_key", "version"],
        unique=True,
    )
    op.create_index(
        "ix_freshness_policy_lookup",
        "freshness_policies",
        ["project_id", "policy_key", "status"],
        unique=False,
    )

    op.create_table(
        "freshness_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assigned_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by", sa.String(length=200), nullable=True),
        sa.Column("retirement_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN topic_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_freshness_assignments_exactly_one_target",
        ),
        sa.CheckConstraint(
            "status in ('active','retired')",
            name="ck_freshness_assignments_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND retired_at IS NULL AND retired_by IS NULL "
            "AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL "
            "AND retired_by IS NOT NULL AND btrim(retired_by) <> '' "
            "AND retirement_reason IS NOT NULL AND btrim(retirement_reason) <> '')",
            name="ck_freshness_assignments_retirement_audit",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["freshness_policies.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["topic_nodes.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(
            ["knowledge_candidate_id"],
            ["knowledge_candidates.id"],
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["freshness_assignments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_freshness_assignment_active_topic",
        "freshness_assignments",
        ["project_id", "topic_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND topic_id IS NOT NULL"),
    )
    op.create_index(
        "uq_freshness_assignment_active_claim",
        "freshness_assignments",
        ["project_id", "claim_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND claim_id IS NOT NULL"),
    )
    op.create_index(
        "uq_freshness_assignment_active_candidate",
        "freshness_assignments",
        ["project_id", "knowledge_candidate_id"],
        unique=True,
        postgresql_where=sa.text(
            "status = 'active' AND knowledge_candidate_id IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_freshness_assignments_policy",
        "freshness_assignments",
        ["project_id", "policy_id", "status"],
        unique=False,
    )

    op.create_table(
        "freshness_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("basis_hash", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("source_documents_json", sa.JSON(), nullable=False),
        sa.Column("observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("verification_method", sa.String(length=32), nullable=False),
        sa.Column("recorded_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_freshness_verifications_exactly_one_target",
        ),
        sa.CheckConstraint(
            "basis_hash ~ '^[0-9a-f]{64}$'",
            name="ck_freshness_verifications_hash",
        ),
        sa.CheckConstraint(
            "verification_method in ('lineage_snapshot')",
            name="ck_freshness_verifications_method",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(
            ["knowledge_candidate_id"],
            ["knowledge_candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_freshness_verification_claim_event",
        "freshness_verifications",
        ["project_id", "claim_id", "basis_hash", "verified_at"],
        unique=True,
        postgresql_where=sa.text("claim_id IS NOT NULL"),
    )
    op.create_index(
        "uq_freshness_verification_candidate_event",
        "freshness_verifications",
        ["project_id", "knowledge_candidate_id", "basis_hash", "verified_at"],
        unique=True,
        postgresql_where=sa.text("knowledge_candidate_id IS NOT NULL"),
    )
    op.create_index(
        "ix_freshness_verifications_claim_time",
        "freshness_verifications",
        ["project_id", "claim_id", "verified_at"],
        unique=False,
    )
    op.create_index(
        "ix_freshness_verifications_candidate_time",
        "freshness_verifications",
        ["project_id", "knowledge_candidate_id", "verified_at"],
        unique=False,
    )

    _create_freshness_guards()

    op.execute(
        sa.text(
            """
            INSERT INTO source_document_observations (
                id,
                source_document_id,
                observed_at,
                content_hash,
                provider,
                reader,
                observation_method,
                created_at,
                updated_at
            )
            SELECT
                md5(sd.id::text || ':' || sd.fetched_at::text)::uuid,
                sd.id,
                sd.fetched_at,
                sd.content_hash,
                sd.provider,
                sd.reader,
                'migration_backfill',
                sd.fetched_at,
                sd.fetched_at
            FROM source_documents sd
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS freshness_verifications_guard "
            "ON freshness_verifications"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_freshness_verification()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS freshness_assignments_guard "
            "ON freshness_assignments"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_freshness_assignment()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS freshness_policies_lifecycle_guard "
            "ON freshness_policies"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS enforce_freshness_policy_lifecycle()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS source_document_observations_guard "
            "ON source_document_observations"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_source_document_observation()"))

    op.drop_index(
        "ix_freshness_verifications_candidate_time",
        table_name="freshness_verifications",
    )
    op.drop_index(
        "ix_freshness_verifications_claim_time",
        table_name="freshness_verifications",
    )
    op.drop_index(
        "uq_freshness_verification_candidate_event",
        table_name="freshness_verifications",
    )
    op.drop_index(
        "uq_freshness_verification_claim_event",
        table_name="freshness_verifications",
    )
    op.drop_table("freshness_verifications")

    op.drop_index("ix_freshness_assignments_policy", table_name="freshness_assignments")
    op.drop_index(
        "uq_freshness_assignment_active_candidate",
        table_name="freshness_assignments",
    )
    op.drop_index(
        "uq_freshness_assignment_active_claim",
        table_name="freshness_assignments",
    )
    op.drop_index(
        "uq_freshness_assignment_active_topic",
        table_name="freshness_assignments",
    )
    op.drop_table("freshness_assignments")

    op.drop_index("ix_freshness_policy_lookup", table_name="freshness_policies")
    op.drop_index("uq_freshness_policy_version", table_name="freshness_policies")
    op.drop_table("freshness_policies")

    op.drop_index(
        "ix_source_document_observations_document_time",
        table_name="source_document_observations",
    )
    op.drop_table("source_document_observations")
