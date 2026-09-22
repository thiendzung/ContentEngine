"""PM-01 durable publication identity models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class PublishedContent(TimestampMixin, Base):
    """Stable mapping from one ContentItem to one external publishing target."""

    __tablename__ = "published_contents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_items.id"), nullable=False
    )
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    current_content_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_versions.id"), nullable=False
    )
    external_revision_id: Mapped[str | None] = mapped_column(String(255))
    external_status: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "content_item_id",
            "target",
            name="uq_published_content_item_target",
        ),
        UniqueConstraint(
            "project_id",
            "target",
            "external_id",
            name="uq_published_content_external_id",
        ),
        CheckConstraint(
            "target in ('wordpress')",
            name="ck_published_content_target",
        ),
        CheckConstraint(
            "external_status in ('draft','publish','future','private')",
            name="ck_published_content_external_status",
        ),
        Index(
            "ix_published_contents_project_url",
            "project_id",
            "canonical_url",
        ),
    )


class PublishEvent(TimestampMixin, Base):
    """Immutable history of one confirmed external draft/publish/update result."""

    __tablename__ = "publish_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    published_content_id: Mapped[UUID] = mapped_column(
        ForeignKey("published_contents.id"), nullable=False
    )
    content_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_versions.id"), nullable=False
    )
    publish_package_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    publish_approval_id: Mapped[UUID] = mapped_column(
        ForeignKey("approvals.id"), nullable=False
    )
    outbox_intent_id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_intents.id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    external_revision_id: Mapped[str | None] = mapped_column(String(255))
    external_status: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_publish_event_idempotency_key"),
        UniqueConstraint("outbox_intent_id", name="uq_publish_event_outbox_intent"),
        CheckConstraint(
            "action in ('draft','publish','update_draft','update_publish')",
            name="ck_publish_event_action",
        ),
        CheckConstraint(
            "external_status in ('draft','publish','future','private')",
            name="ck_publish_event_external_status",
        ),
        Index(
            "ix_publish_events_content_version",
            "content_version_id",
            "created_at",
        ),
    )


__all__ = ["PublishedContent", "PublishEvent"]
