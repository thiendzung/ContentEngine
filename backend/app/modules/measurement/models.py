"""PM-01 normalized post-publication measurement models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
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