from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

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


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> UUID:
    return uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    default_locale: Mapped[str] = mapped_column(String(32), nullable=False, default="en")


class AudienceHypothesis(TimestampMixin, Base):
    __tablename__ = "audience_hypotheses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (Index("ix_audience_hypotheses_project", "project_id"),)


class Signal(TimestampMixin, Base):
    __tablename__ = "signals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    duplicate_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("signals.id"))
    independence_group: Mapped[str | None] = mapped_column(String(255))
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source_kind in ('MARKET','SEARCH','MOTGU')",
            name="ck_signals_source_kind",
        ),
        CheckConstraint(
            "scope in ('market_web','motgu_site','motgu_direct')",
            name="ck_signals_scope",
        ),
        Index("ix_signals_project_fingerprint", "project_id", "fingerprint"),
    )


class NeedHypothesis(TimestampMixin, Base):
    __tablename__ = "need_hypotheses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    audience_hypothesis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("audience_hypotheses.id")
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    audience_scope: Mapped[str] = mapped_column(Text, nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    alternative_explanations_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status in ('PROPOSED','TESTING','SUPPORTED','REJECTED','INSUFFICIENT_EVIDENCE')",
            name="ck_need_hypotheses_status",
        ),
        CheckConstraint("version > 0", name="ck_need_hypotheses_version_positive"),
        Index("ix_need_hypotheses_project", "project_id"),
    )


class NeedHypothesisSignal(Base):
    __tablename__ = "need_hypothesis_signals"

    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id", ondelete="CASCADE"), primary_key=True
    )
    signal_id: Mapped[UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(16), primary_key=True)

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts')",
            name="ck_need_hypothesis_signals_relation",
        ),
    )


class NeedHypothesisReview(TimestampMixin, Base):
    __tablename__ = "need_hypothesis_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    support_signal_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    contradict_signal_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        UniqueConstraint(
            "need_hypothesis_id",
            "version",
            name="uq_need_hypothesis_review_version",
        ),
    )


class ContentOpportunity(TimestampMixin, Base):
    __tablename__ = "content_opportunities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    reader: Mapped[str] = mapped_column(Text, nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    need: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    promise: Mapped[str] = mapped_column(Text, nullable=False)
    motgu_material_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    material_gaps_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    existing_content_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    what_is_actually_new: Mapped[str] = mapped_column(Text, nullable=False)
    next_discovery_step: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    suggested_content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    suggested_role: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected_by: Mapped[str | None] = mapped_column(String(200))
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selection_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "decision in ('CREATE','UPDATE','REFRESH','MERGE','LINK_ONLY','DO_NOT_WRITE')",
            name="ck_content_opportunities_decision",
        ),
        CheckConstraint(
            "priority in ('NOW','NEXT','LATER','NO')",
            name="ck_content_opportunities_priority",
        ),
        CheckConstraint(
            "decision not in ('UPDATE','REFRESH','MERGE','LINK_ONLY') "
            "or json_array_length(existing_content_refs_json) > 0",
            name="ck_content_opportunities_existing_target",
        ),
        CheckConstraint("version > 0", name="ck_content_opportunities_version_positive"),
        Index("ix_content_opportunities_project", "project_id"),
    )


class ContentOpportunitySignal(Base):
    __tablename__ = "content_opportunity_signals"

    content_opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_opportunities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    signal_id: Mapped[UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )


class HumanSelection(TimestampMixin, Base):
    __tablename__ = "human_selections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_opportunities.id"), nullable=False
    )
    selected_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (Index("ix_human_selections_opportunity", "content_opportunity_id"),)


class ContentExperiment(TimestampMixin, Base):
    __tablename__ = "content_experiments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_opportunities.id"), nullable=False
    )
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id"), nullable=False
    )
    hypothesis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_behaviour: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_plan_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metric_definitions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    minimum_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    review_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    observation_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    alternative_explanations_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status in ('PLANNED','RUNNING','REVIEWED')",
            name="ck_content_experiments_status",
        ),
        CheckConstraint(
            "result in ('PENDING','SUPPORTS','CONTRADICTS','INCONCLUSIVE')",
            name="ck_content_experiments_result",
        ),
        CheckConstraint(
            "hypothesis_version > 0",
            name="ck_content_experiment_hypothesis_version",
        ),
    )


class ContentCase(TimestampMixin, Base):
    __tablename__ = "content_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_hypothesis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("audience_hypotheses.id")
    )
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id"), nullable=False
    )
    content_opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_opportunities.id"), nullable=False
    )
    desired_action: Mapped[str] = mapped_column(Text, nullable=False)
    content_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    originality_statement: Mapped[str] = mapped_column(Text, nullable=False)
    reader_before: Mapped[str] = mapped_column(Text, nullable=False)
    reader_after: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    __table_args__ = (
        CheckConstraint(
            "content_type in ('journal','artwork')",
            name="ck_content_cases_type",
        ),
        Index("ix_content_cases_project", "project_id"),
    )


class LocaleVariant(TimestampMixin, Base):
    __tablename__ = "locale_variants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_case_id: Mapped[UUID] = mapped_column(ForeignKey("content_cases.id"), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    content_role: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_question: Mapped[str] = mapped_column(Text, nullable=False)
    primary_intent: Mapped[str] = mapped_column(String(64), nullable=False)
    secondary_intent: Mapped[str | None] = mapped_column(String(64))
    primary_query: Mapped[str | None] = mapped_column(Text)
    keyword_notes_json: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    emotion_arc_json: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    must_include_json: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    must_not_claim_json: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    __table_args__ = (
        UniqueConstraint("content_case_id", "locale", name="uq_locale_variant_case_locale"),
    )


class ContentItem(TimestampMixin, Base):
    __tablename__ = "content_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_case_id: Mapped[UUID] = mapped_column(ForeignKey("content_cases.id"), nullable=False)
    locale_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("locale_variants.id"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "canonical_key", name="uq_content_item_canonical_key"),
        UniqueConstraint("locale_variant_id", name="uq_content_item_locale_variant"),
        CheckConstraint(
            "content_type in ('journal','artwork')",
            name="ck_content_items_type",
        ),
    )


class ContentVersion(TimestampMixin, Base):
    __tablename__ = "content_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_item_id: Mapped[UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("content_item_id", "version_no", name="uq_content_version_number"),
        CheckConstraint("version_no > 0", name="ck_content_version_positive"),
        CheckConstraint(
            "status in ('draft','approved','published','superseded')",
            name="ck_content_version_status",
        ),
        Index("ix_content_versions_item", "content_item_id"),
    )


class SettingsVersion(TimestampMixin, Base):
    __tablename__ = "settings_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    settings_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint(
            "project_id", "scope_type", "scope_key", "version", name="uq_settings_version"
        ),
        CheckConstraint(
            "scope_type in ('system','project','content_type','locale')", name="ck_settings_scope"
        ),
        CheckConstraint("status in ('draft','active','retired')", name="ck_settings_status"),
        CheckConstraint("version > 0", name="ck_settings_version_positive"),
    )


class SettingsSnapshot(TimestampMixin, Base):
    __tablename__ = "settings_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    resolved_settings_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_version_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class PromptDefinition(TimestampMixin, Base):
    __tablename__ = "prompt_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    prompt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    input_contract_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    output_schema_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_prompt_definition_version"),
        CheckConstraint("status in ('draft','active','retired')", name="ck_prompt_status"),
        CheckConstraint("version > 0", name="ck_prompt_version_positive"),
    )


class RecipeDefinition(TimestampMixin, Base):
    __tablename__ = "recipe_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    recipe_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    recipe_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("recipe_key", "version", name="uq_recipe_definition_version"),
        CheckConstraint("status in ('draft','active','retired')", name="ck_recipe_status"),
        CheckConstraint("version > 0", name="ck_recipe_version_positive"),
    )


class CalibrationExample(TimestampMixin, Base):
    __tablename__ = "calibration_examples"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(32))
    intent: Mapped[str | None] = mapped_column(String(64))
    example_type: Mapped[str] = mapped_column(String(32), nullable=False)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    approved_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("polarity in ('positive','negative')", name="ck_calibration_polarity"),
        CheckConstraint(
            "status in ('candidate','approved','retired')", name="ck_calibration_status"
        ),
    )


def register_models() -> None:
    """Import hook used by migration metadata discovery."""
    from app.modules.harness import models as _harness_models  # noqa: F401
    from app.modules.knowledge import models as _knowledge_models  # noqa: F401
