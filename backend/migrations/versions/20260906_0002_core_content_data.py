"""CE02 PR-A core content data.

Revision ID: 20260906_0002
Revises: 20260902_0001
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260906_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("default_locale", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )

    op.create_table(
        "audience_hypotheses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("confidence", sa.String(length=32)),
        *_timestamps(),
    )
    op.create_index(
        "ix_audience_hypotheses_project",
        "audience_hypotheses",
        ["project_id"],
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("observed_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("external_id", sa.String(length=255)),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("duplicate_of_id", sa.Uuid(), sa.ForeignKey("signals.id")),
        sa.Column("independence_group", sa.String(length=255)),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "source_kind in ('MARKET','SEARCH','MOTGU')",
            name="ck_signals_source_kind",
        ),
        sa.CheckConstraint(
            "scope in ('market_web','motgu_site','motgu_direct')",
            name="ck_signals_scope",
        ),
    )
    op.create_index(
        "ix_signals_project_fingerprint",
        "signals",
        ["project_id", "fingerprint"],
    )

    op.create_table(
        "need_hypotheses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "audience_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("audience_hypotheses.id"),
        ),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("audience_scope", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("alternative_explanations_json", sa.JSON(), nullable=False),
        sa.Column("missing_evidence_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_reason", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "status in ('PROPOSED','TESTING','SUPPORTED','REJECTED',"
            "'INSUFFICIENT_EVIDENCE')",
            name="ck_need_hypotheses_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_need_hypotheses_version_positive",
        ),
    )
    op.create_index("ix_need_hypotheses_project", "need_hypotheses", ["project_id"])

    op.create_table(
        "need_hypothesis_signals",
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "signal_id",
            sa.Uuid(),
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relation", sa.String(length=16), primary_key=True),
        sa.CheckConstraint(
            "relation in ('supports','contradicts')",
            name="ck_need_hypothesis_signals_relation",
        ),
    )

    op.create_table(
        "need_hypothesis_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("support_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("contradict_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "need_hypothesis_id",
            "version",
            name="uq_need_hypothesis_review_version",
        ),
    )

    op.create_table(
        "content_opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("reader", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("need", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("promise", sa.Text(), nullable=False),
        sa.Column("motgu_material_refs_json", sa.JSON(), nullable=False),
        sa.Column("material_gaps_json", sa.JSON(), nullable=False),
        sa.Column("existing_content_refs_json", sa.JSON(), nullable=False),
        sa.Column("what_is_actually_new", sa.Text(), nullable=False),
        sa.Column("next_discovery_step", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("suggested_content_type", sa.String(length=32), nullable=False),
        sa.Column("suggested_role", sa.String(length=32)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("selected_by", sa.String(length=200)),
        sa.Column("selected_at", sa.DateTime(timezone=True)),
        sa.Column("selection_reason", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "decision in ('CREATE','UPDATE','REFRESH','MERGE','LINK_ONLY','DO_NOT_WRITE')",
            name="ck_content_opportunities_decision",
        ),
        sa.CheckConstraint(
            "priority in ('NOW','NEXT','LATER','NO')",
            name="ck_content_opportunities_priority",
        ),
        sa.CheckConstraint(
            "decision not in ('UPDATE','REFRESH','MERGE','LINK_ONLY') "
            "or json_array_length(existing_content_refs_json) > 0",
            name="ck_content_opportunities_existing_target",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_content_opportunities_version_positive",
        ),
    )
    op.create_index(
        "ix_content_opportunities_project",
        "content_opportunities",
        ["project_id"],
    )

    op.create_table(
        "content_opportunity_signals",
        sa.Column(
            "content_opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("content_opportunities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "signal_id",
            sa.Uuid(),
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "human_selections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("content_opportunities.id"),
            nullable=False,
        ),
        sa.Column("selected_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_human_selections_opportunity",
        "human_selections",
        ["content_opportunity_id"],
    )

    op.create_table(
        "content_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "content_opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("content_opportunities.id"),
            nullable=False,
        ),
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id"),
            nullable=False,
        ),
        sa.Column("hypothesis_version", sa.Integer(), nullable=False),
        sa.Column("expected_behaviour", sa.Text(), nullable=False),
        sa.Column("measurement_plan_json", sa.JSON(), nullable=False),
        sa.Column("metric_definitions_json", sa.JSON(), nullable=False),
        sa.Column("minimum_evidence_json", sa.JSON(), nullable=False),
        sa.Column("review_window_start", sa.DateTime(timezone=True)),
        sa.Column("review_window_end", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("observation_refs_json", sa.JSON(), nullable=False),
        sa.Column("alternative_explanations_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status in ('PLANNED','RUNNING','REVIEWED')",
            name="ck_content_experiments_status",
        ),
        sa.CheckConstraint(
            "result in ('PENDING','SUPPORTS','CONTRADICTS','INCONCLUSIVE')",
            name="ck_content_experiments_result",
        ),
        sa.CheckConstraint(
            "hypothesis_version > 0",
            name="ck_content_experiment_hypothesis_version",
        ),
    )

    op.create_table(
        "content_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column(
            "audience_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("audience_hypotheses.id"),
        ),
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id"),
            nullable=False,
        ),
        sa.Column(
            "content_opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("content_opportunities.id"),
            nullable=False,
        ),
        sa.Column("desired_action", sa.Text(), nullable=False),
        sa.Column("content_hypothesis", sa.Text(), nullable=False),
        sa.Column("originality_statement", sa.Text(), nullable=False),
        sa.Column("reader_before", sa.Text(), nullable=False),
        sa.Column("reader_after", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "content_type in ('journal','artwork')",
            name="ck_content_cases_type",
        ),
    )
    op.create_index("ix_content_cases_project", "content_cases", ["project_id"])

    op.create_table(
        "locale_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_case_id",
            sa.Uuid(),
            sa.ForeignKey("content_cases.id"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("content_role", sa.String(length=32), nullable=False),
        sa.Column("primary_question", sa.Text(), nullable=False),
        sa.Column("primary_intent", sa.String(length=64), nullable=False),
        sa.Column("secondary_intent", sa.String(length=64)),
        sa.Column("primary_query", sa.Text()),
        sa.Column("keyword_notes_json", sa.JSON(), nullable=False),
        sa.Column("emotion_arc_json", sa.JSON(), nullable=False),
        sa.Column("must_include_json", sa.JSON(), nullable=False),
        sa.Column("must_not_claim_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "content_case_id",
            "locale",
            name="uq_locale_variant_case_locale",
        ),
    )

    op.create_table(
        "content_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), sa.ForeignKey("content_cases.id"), nullable=False),
        sa.Column(
            "locale_variant_id",
            sa.Uuid(),
            sa.ForeignKey("locale_variants.id"),
            nullable=False,
        ),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("canonical_key", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "project_id",
            "canonical_key",
            name="uq_content_item_canonical_key",
        ),
        sa.UniqueConstraint(
            "locale_variant_id",
            name="uq_content_item_locale_variant",
        ),
        sa.CheckConstraint(
            "content_type in ('journal','artwork')",
            name="ck_content_items_type",
        ),
    )

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.Uuid(),
            sa.ForeignKey("content_items.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "content_item_id",
            "version_no",
            name="uq_content_version_number",
        ),
        sa.CheckConstraint(
            "version_no > 0",
            name="ck_content_version_positive",
        ),
        sa.CheckConstraint(
            "status in ('draft','approved','published','superseded')",
            name="ck_content_version_status",
        ),
    )
    op.create_index("ix_content_versions_item", "content_versions", ["content_item_id"])


def downgrade() -> None:
    op.drop_index("ix_content_versions_item", table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_table("content_items")
    op.drop_table("locale_variants")
    op.drop_index("ix_content_cases_project", table_name="content_cases")
    op.drop_table("content_cases")
    op.drop_table("content_experiments")
    op.drop_index("ix_human_selections_opportunity", table_name="human_selections")
    op.drop_table("human_selections")
    op.drop_table("content_opportunity_signals")
    op.drop_index("ix_content_opportunities_project", table_name="content_opportunities")
    op.drop_table("content_opportunities")
    op.drop_table("need_hypothesis_reviews")
    op.drop_table("need_hypothesis_signals")
    op.drop_index("ix_need_hypotheses_project", table_name="need_hypotheses")
    op.drop_table("need_hypotheses")
    op.drop_index("ix_signals_project_fingerprint", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_audience_hypotheses_project", table_name="audience_hypotheses")
    op.drop_table("audience_hypotheses")
    op.drop_table("projects")
