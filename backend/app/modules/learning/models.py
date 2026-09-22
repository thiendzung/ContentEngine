"""LL-01B durable learning-candidate models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class LearningCandidate(TimestampMixin, Base):
    """Versioned proposal derived from reviewed measurement evidence.

    A LearningCandidate is not Customer Truth. LL-01C owns human review and any
    later Customer Map application.
    """

    __tablename__ = "learning_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    candidate_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)
    proposal_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    scope_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    alternative_explanations_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_evidence_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    expected_benefit: Mapped[str | None] = mapped_column(Text)
    regression_risk: Mapped[str | None] = mapped_column(Text)
    source_assessment_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_candidates.id")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")

    __table_args__ = (
        CheckConstraint(
            "candidate_key ~ '^[0-9a-f]{64}$'",
            name="ck_learning_candidates_key",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_learning_candidates_version_positive",
        ),
        CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_candidates_target_type",
        ),
        CheckConstraint(
            "relation in ('supports','contradicts','context','proposes','no_change')",
            name="ck_learning_candidates_relation",
        ),
        CheckConstraint(
            "evidence_status in "
            "('NEEDS_EVIDENCE','EARLY_SIGNAL','REPEATED_PATTERN',"
            "'CONTESTED','READY_FOR_REVIEW')",
            name="ck_learning_candidates_evidence_status",
        ),
        CheckConstraint(
            "status in ('OPEN','SUPERSEDED','ARCHIVED')",
            name="ck_learning_candidates_status",
        ),
        UniqueConstraint(
            "project_id",
            "candidate_key",
            "version",
            name="uq_learning_candidate_project_key_version",
        ),
        Index(
            "ix_learning_candidates_project_status",
            "project_id",
            "status",
            "evidence_status",
        ),
        Index(
            "ix_learning_candidates_target",
            "target_type",
            "target_id",
        ),
    )


class LearningCandidateReview(TimestampMixin, Base):
    """One immutable human review decision for an exact candidate version."""

    __tablename__ = "learning_candidate_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    learning_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidates.id"), nullable=False
    )
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_snapshot_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "decision in "
            "('APPROVE','REJECT','REQUEST_MORE_EVIDENCE','NO_MAP_CHANGE')",
            name="ck_learning_candidate_reviews_decision",
        ),
        CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_candidate_reviews_version",
        ),
        CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_candidate_reviews_snapshot_hash",
        ),
        UniqueConstraint(
            "learning_candidate_id",
            name="uq_learning_candidate_review_candidate",
        ),
        Index(
            "ix_learning_candidate_reviews_project_time",
            "project_id",
            "reviewed_at",
        ),
    )


class LearningApplication(TimestampMixin, Base):
    """Immutable receipt proving one approved learning application."""

    __tablename__ = "learning_applications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    learning_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidates.id"), nullable=False
    )
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidate_reviews.id"), nullable=False
    )
    candidate_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    resulting_target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    applied_action: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_signal_refs_json: Mapped[list[object]] = mapped_column(
        JSON, nullable=False, default=list
    )
    frozen_scope_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False
    )
    before_state_hash: Mapped[str | None] = mapped_column(String(64))
    after_state_hash: Mapped[str | None] = mapped_column(String(64))
    customer_map_snapshot_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("artifacts.id")
    )
    change_report_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    applied_by: Mapped[str] = mapped_column(String(200), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_applications_version",
        ),
        CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_applications_snapshot_hash",
        ),
        CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_applications_target_type",
        ),
        CheckConstraint(
            "applied_action in "
            "('link_need_signals','link_insight_signals',"
            "'create_candidate_insight','no_map_change')",
            name="ck_learning_applications_action",
        ),
        UniqueConstraint(
            "review_id",
            name="uq_learning_application_review",
        ),
        Index(
            "ix_learning_applications_candidate",
            "learning_candidate_id",
            "candidate_version",
        ),
        Index(
            "ix_learning_applications_project_time",
            "project_id",
            "applied_at",
        ),
    )


class LearningCandidateAssessment(Base):
    """Immutable assessment evidence bound to one candidate version."""

    __tablename__ = "learning_candidate_assessments"

    learning_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assessment_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"),
        primary_key=True,
    )

    __table_args__ = (
        Index(
            "ix_learning_candidate_assessments_artifact",
            "assessment_artifact_id",
            "learning_candidate_id",
        ),
    )


class LearningCandidateSignal(Base):
    """Immutable factual Signal evidence for one candidate version."""

    __tablename__ = "learning_candidate_signals"

    learning_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    signal_id: Mapped[UUID] = mapped_column(
        ForeignKey("signals.id"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_learning_candidate_signals_relation",
        ),
        Index(
            "ix_learning_candidate_signals_signal",
            "signal_id",
            "relation",
        ),
    )


class LearningCandidateObservation(Base):
    """Immutable measurement-observation evidence for one candidate version."""

    __tablename__ = "learning_candidate_observations"

    learning_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_candidates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_performance_observations.id"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_learning_candidate_observations_relation",
        ),
        Index(
            "ix_learning_candidate_observations_observation",
            "observation_id",
            "relation",
        ),
    )


__all__ = [
    "LearningApplication",
    "LearningCandidate",
    "LearningCandidateAssessment",
    "LearningCandidateObservation",
    "LearningCandidateReview",
    "LearningCandidateSignal",
]
