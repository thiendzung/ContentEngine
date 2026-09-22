"""PM-01 normalized post-publication measurement models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id

CORE_METRICS = (
    "impressions",
    "clicks",
    "sessions",
    "engaged_sessions",
    "artwork_transition",
    "visit_transition",
    "workshop_transition",
    "inquiry",
)


class PerformanceSnapshot(TimestampMixin, Base):
    """Auditable provider window and bounded raw payload."""

    __tablename__ = "performance_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    published_content_id: Mapped[UUID] = mapped_column(
        ForeignKey("published_contents.id"), nullable=False
    )
    content_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_versions.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "published_content_id",
            "provider",
            "window_start",
            "window_end",
            "payload_fingerprint",
            name="uq_performance_snapshot_identity",
        ),
        CheckConstraint(
            "provider in ('search_console','analytics','motgu_conversion','rank_math')",
            name="ck_performance_snapshot_provider",
        ),
        CheckConstraint(
            "window_end >= window_start",
            name="ck_performance_snapshot_window",
        ),
        Index(
            "ix_performance_snapshots_published_window",
            "published_content_id",
            "window_end",
        ),
    )


class PerformanceMetric(TimestampMixin, Base):
    """Normalized comparable metric row."""

    __tablename__ = "performance_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("performance_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    published_content_id: Mapped[UUID] = mapped_column(
        ForeignKey("published_contents.id"), nullable=False
    )
    content_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_versions.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    dimensions_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "metric_name in ("
            "'impressions','clicks','sessions','engaged_sessions',"
            "'artwork_transition','visit_transition','workshop_transition','inquiry'"
            ")",
            name="ck_performance_metric_name",
        ),
        CheckConstraint(
            "metric_value >= 0",
            name="ck_performance_metric_nonnegative",
        ),
        UniqueConstraint(
            "snapshot_id",
            "metric_date",
            "metric_name",
            name="uq_performance_metric_snapshot_date_name",
        ),
        Index(
            "ix_performance_metrics_content_name_date",
            "published_content_id",
            "metric_name",
            "metric_date",
        ),
    )


class ContentPerformanceObservation(TimestampMixin, Base):
    """Structured interpretation of metrics; not a learning rule."""

    __tablename__ = "content_performance_observations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    published_content_id: Mapped[UUID] = mapped_column(
        ForeignKey("published_contents.id"), nullable=False
    )
    content_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_versions.id"), nullable=False
    )
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "data_status in ("
            "'INSUFFICIENT_DATA','EARLY_SIGNAL','REPEATED_PATTERN',"
            "'LEARNING_CANDIDATE_READY'"
            ")",
            name="ck_content_performance_observation_status",
        ),
        Index(
            "ix_content_performance_observation_content",
            "published_content_id",
            "observed_at",
        ),
    )


__all__ = [
    "CORE_METRICS",
    "ContentPerformanceObservation",
    "PerformanceMetric",
    "PerformanceSnapshot",
]