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
from app.modules.content_engine.models import TimestampMixin, new_id, utc_now


class CustomerInsight(TimestampMixin, Base):
    __tablename__ = "customer_insights"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    insight_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    audience_hypothesis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("audience_hypotheses.id")
    )
    insight_type: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    situation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CANDIDATE"
    )
    alternative_explanations_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_evidence_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "insight_key ~ '^[0-9a-f]{64}$'",
            name="ck_customer_insights_key",
        ),
        CheckConstraint(
            "insight_type in "
            "('job','pain','desire','question','fear','objection','barrier',"
            "'trigger','decision_factor','trust_builder','trust_breaker','language',"
            "'behaviour','expectation','post_purchase_need','referral_trigger',"
            "'repeat_purchase_trigger')",
            name="ck_customer_insights_type",
        ),
        CheckConstraint(
            "status in "
            "('CANDIDATE','TESTING','SUPPORTED','REJECTED',"
            "'INSUFFICIENT_EVIDENCE')",
            name="ck_customer_insights_status",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_customer_insights_version_positive",
        ),
        UniqueConstraint(
            "project_id",
            "insight_key",
            "version",
            name="uq_customer_insight_project_key_version",
        ),
        Index(
            "ix_customer_insights_project_type",
            "project_id",
            "insight_type",
            "status",
        ),
        Index(
            "ix_customer_insights_audience",
            "audience_hypothesis_id",
        ),
    )


class CustomerInsightSignal(Base):
    __tablename__ = "customer_insight_signals"

    customer_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_insights.id", ondelete="CASCADE"),
        primary_key=True,
    )
    signal_id: Mapped[UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_customer_insight_signals_relation",
        ),
        Index(
            "ix_customer_insight_signals_signal",
            "signal_id",
            "relation",
        ),
    )





class CustomerInsightNeedLink(Base):
    __tablename__ = "customer_insight_need_links"

    customer_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_insights.id", ondelete="CASCADE"),
        primary_key=True,
    )
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_customer_insight_need_links_relation",
        ),
        Index(
            "ix_customer_insight_need_links_need",
            "need_hypothesis_id",
            "relation",
        ),
    )


class CustomerNeedJourneyStageLink(Base):
    __tablename__ = "customer_need_journey_stage_links"

    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "stage_key ~ '^[a-z0-9][a-z0-9_-]{0,63}    __tablename__ = "customer_insight_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    customer_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    support_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    contradict_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    context_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "status in "
            "('TESTING','SUPPORTED','REJECTED','INSUFFICIENT_EVIDENCE')",
            name="ck_customer_insight_reviews_status",
        ),
        Index(
            "ix_customer_insight_reviews_insight_time",
            "customer_insight_id",
            "reviewed_at",
        ),
    )


__all__ = [
    "CustomerInsight",
    "CustomerInsightNeedLink",
    "CustomerInsightReview",
    "CustomerNeedJourneyStageLink",
    "CustomerInsightSignal",
]",
            name="ck_customer_need_journey_stage_key",
        ),
        Index(
            "ix_customer_need_journey_stage",
            "stage_key",
            "need_hypothesis_id",
        ),
    )


class CustomerInsightReview(Base):
    __tablename__ = "customer_insight_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    customer_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    support_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    contradict_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    context_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "status in "
            "('TESTING','SUPPORTED','REJECTED','INSUFFICIENT_EVIDENCE')",
            name="ck_customer_insight_reviews_status",
        ),
        Index(
            "ix_customer_insight_reviews_insight_time",
            "customer_insight_id",
            "reviewed_at",
        ),
    )


__all__ = [
    "CustomerInsight",
    "CustomerInsightNeedLink",
    "CustomerInsightReview",
    "CustomerInsightSignal",
]