from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class FreshnessPolicy(TimestampMixin, Base):
    __tablename__ = "freshness_policies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    freshness_class: Mapped[str] = mapped_column(String(16), nullable=False)
    max_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    refresh_lead_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "freshness_class in ('evergreen','slow','medium','fast')",
            name="ck_freshness_policies_class",
        ),
        CheckConstraint(
            "max_age_days >= 1 and max_age_days <= 3650",
            name="ck_freshness_policies_max_age",
        ),
        CheckConstraint(
            "refresh_lead_days >= 0 and refresh_lead_days < max_age_days",
            name="ck_freshness_policies_refresh_lead",
        ),
        CheckConstraint(
            "status in ('active','retired')",
            name="ck_freshness_policies_status",
        ),
        CheckConstraint("version > 0", name="ck_freshness_policies_version"),
        Index(
            "uq_freshness_policy_version",
            "project_id",
            "policy_key",
            "version",
            unique=True,
        ),
        Index("ix_freshness_policy_lookup", "project_id", "policy_key", "status"),
    )


class FreshnessAssignment(TimestampMixin, Base):
    __tablename__ = "freshness_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("freshness_policies.id"), nullable=False)
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic_nodes.id"))
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    knowledge_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_candidates.id")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    assigned_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("freshness_assignments.id"))

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN topic_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_freshness_assignments_exactly_one_target",
        ),
        CheckConstraint(
            "status in ('active','retired')",
            name="ck_freshness_assignments_status",
        ),
        Index(
            "uq_freshness_assignment_active_topic",
            "project_id",
            "topic_id",
            unique=True,
            postgresql_where=text("status = 'active' AND topic_id IS NOT NULL"),
        ),
        Index(
            "uq_freshness_assignment_active_claim",
            "project_id",
            "claim_id",
            unique=True,
            postgresql_where=text("status = 'active' AND claim_id IS NOT NULL"),
        ),
        Index(
            "uq_freshness_assignment_active_candidate",
            "project_id",
            "knowledge_candidate_id",
            unique=True,
            postgresql_where=text(
                "status = 'active' AND knowledge_candidate_id IS NOT NULL"
            ),
        ),
        Index("ix_freshness_assignments_policy", "project_id", "policy_id", "status"),
    )


class FreshnessVerification(TimestampMixin, Base):
    __tablename__ = "freshness_verifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    knowledge_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_candidates.id")
    )
    basis_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_documents_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    verification_method: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_freshness_verifications_exactly_one_target",
        ),
        CheckConstraint(
            "basis_hash ~ '^[0-9a-f]{64}$'",
            name="ck_freshness_verifications_hash",
        ),
        CheckConstraint(
            "verification_method in ('lineage_snapshot')",
            name="ck_freshness_verifications_method",
        ),
        Index(
            "uq_freshness_verification_claim_basis",
            "project_id",
            "claim_id",
            "basis_hash",
            unique=True,
            postgresql_where=text("claim_id IS NOT NULL"),
        ),
        Index(
            "uq_freshness_verification_candidate_basis",
            "project_id",
            "knowledge_candidate_id",
            "basis_hash",
            unique=True,
            postgresql_where=text("knowledge_candidate_id IS NOT NULL"),
        ),
        Index(
            "ix_freshness_verifications_claim_time",
            "project_id",
            "claim_id",
            "verified_at",
        ),
        Index(
            "ix_freshness_verifications_candidate_time",
            "project_id",
            "knowledge_candidate_id",
            "verified_at",
        ),
    )
