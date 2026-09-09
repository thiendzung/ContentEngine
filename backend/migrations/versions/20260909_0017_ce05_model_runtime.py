"""Harden CE05 settings and add the provider-neutral agent runtime contract."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0017"
down_revision: str | None = "20260909_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROJECT_ID = "00000000-0000-0000-0000-000000000001"
_SETTINGS_ID = "00000000-0000-0000-0000-000000000014"
_PROMPT_ID = "00000000-0000-0000-0000-000000000022"
_RECIPE_ID = "00000000-0000-0000-0000-000000000032"


def _immutable_trigger(
    *,
    function_name: str,
    trigger_name: str,
    table_name: str,
    fields: tuple[str, ...],
) -> None:
    comparisons = " OR ".join(
        f"NEW.{field}::text IS DISTINCT FROM OLD.{field}::text" if field.endswith("_json")
        else f"NEW.{field} IS DISTINCT FROM OLD.{field}"
        for field in fields
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {function_name}() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' AND OLD.status = 'active' THEN
                    RAISE EXCEPTION '{table_name}_active_is_immutable';
                END IF;
                IF TG_OP = 'UPDATE' AND OLD.status = 'active' AND (
                    NEW.status <> 'retired' OR {comparisons}
                ) THEN
                    RAISE EXCEPTION '{table_name}_active_is_immutable';
                END IF;
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION {function_name}()
            """
        )
    )


def _drop_immutable_trigger(*, function_name: str, trigger_name: str, table_name: str) -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {function_name}()"))


def upgrade() -> None:
    op.add_column(
        "model_calls",
        sa.Column("runtime_metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "uq_active_settings_project_scope",
        "settings_versions",
        ["project_id", "scope_type", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND project_id IS NOT NULL"),
    )
    op.create_index(
        "uq_active_settings_system_scope",
        "settings_versions",
        ["scope_type", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND project_id IS NULL"),
    )
    op.create_index(
        "uq_active_prompt_key",
        "prompt_definitions",
        ["prompt_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_active_recipe_key",
        "recipe_definitions",
        ["recipe_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    _immutable_trigger(
        function_name="prevent_active_settings_version_mutation",
        trigger_name="settings_versions_active_immutable",
        table_name="settings_versions",
        fields=(
            "project_id",
            "scope_type",
            "scope_key",
            "version",
            "settings_json",
            "change_reason",
            "approved_by",
        ),
    )
    _immutable_trigger(
        function_name="prevent_active_prompt_mutation",
        trigger_name="prompt_definitions_active_immutable",
        table_name="prompt_definitions",
        fields=(
            "prompt_key",
            "version",
            "purpose",
            "body",
            "input_contract_json",
            "output_schema_json",
            "change_reason",
            "approved_by",
        ),
    )
    _immutable_trigger(
        function_name="prevent_active_recipe_mutation",
        trigger_name="recipe_definitions_active_immutable",
        table_name="recipe_definitions",
        fields=(
            "recipe_key",
            "version",
            "selector_json",
            "recipe_json",
            "approved_by",
        ),
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    settings = sa.table(
        "settings_versions",
        sa.column("id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("scope_type", sa.String()),
        sa.column("scope_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("settings_json", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("change_reason", sa.Text()),
        sa.column("approved_by", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        settings,
        [
            {
                "id": _SETTINGS_ID,
                "project_id": _PROJECT_ID,
                "scope_type": "content_type",
                "scope_key": "journal",
                "version": 1,
                "settings_json": {
                    "models": {"angle": {"route": "agent_angle"}},
                    "model_routes": {
                        "agent_angle": {
                            "provider": "codex_cli",
                            "model": "pending_human_selection",
                        }
                    },
                },
                "status": "draft",
                "change_reason": "CE05 PR-B.2A draft agent Angle route; human selection required",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    prompt = sa.table(
        "prompt_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("prompt_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("purpose", sa.Text()),
        sa.column("body", sa.Text()),
        sa.column("input_contract_json", sa.JSON()),
        sa.column("output_schema_json", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("change_reason", sa.Text()),
        sa.column("approved_by", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    candidate_fields = [
        "angle_id",
        "working_title",
        "reader_problem",
        "central_question",
        "core_promise",
        "point_of_view",
        "why_now",
        "evidence_refs",
        "originality_refs",
        "excluded_claims",
        "risks",
        "confidence",
        "locale",
    ]
    op.bulk_insert(
        prompt,
        [
            {
                "id": _PROMPT_ID,
                "prompt_key": "journal_angle_candidates",
                "version": 1,
                "purpose": "Generate grounded Journal Angle candidates for human selection.",
                "body": (
                    "Return JSON only. Generate 3 to 5 meaningfully different Angle candidates. "
                    "Use only the supplied Opportunity, locked EvidenceSet, approved OriginalityPack "
                    "and ContextManifest references. Do not invent facts, claims, sources, or approval. "
                    "Every evidence_refs and originality_refs value must be copied from supplied input. "
                    "Keep the reader problem and promise useful for the supplied locale."
                ),
                "input_contract_json": {
                    "required": [
                        "input_bundle_ref",
                        "opportunity",
                        "evidence_set",
                        "originality_pack",
                    ],
                    "forbidden": [
                        "raw_provider_payload",
                        "search_snippets",
                        "repository_context",
                        "secrets",
                    ],
                },
                "output_schema_json": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["candidates"],
                    "properties": {
                        "candidates": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": candidate_fields,
                                "properties": {
                                    "angle_id": {"type": "string", "minLength": 1},
                                    "working_title": {"type": "string", "minLength": 1},
                                    "reader_problem": {"type": "string", "minLength": 1},
                                    "central_question": {"type": "string", "minLength": 1},
                                    "core_promise": {"type": "string", "minLength": 1},
                                    "point_of_view": {"type": "string", "minLength": 1},
                                    "why_now": {"type": "string", "minLength": 1},
                                    "evidence_refs": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "originality_refs": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "excluded_claims": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "risks": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                    "locale": {"type": "string", "minLength": 1},
                                },
                            },
                        }
                    },
                },
                "status": "draft",
                "change_reason": "CE05 PR-B.2A draft Angle generator prompt; human activation required",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    recipe = sa.table(
        "recipe_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("recipe_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("selector_json", sa.JSON()),
        sa.column("recipe_json", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("approved_by", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        recipe,
        [
            {
                "id": _RECIPE_ID,
                "recipe_key": "journal_angle_v1",
                "version": 1,
                "selector_json": {"content_type": "journal", "task": "angle"},
                "recipe_json": {
                    "steps": [
                        "reader_problem",
                        "central_question",
                        "core_promise",
                        "point_of_view",
                        "why_now",
                    ],
                    "constraints": [
                        "grounded_in_supplied_evidence",
                        "grounded_in_approved_originality",
                        "no_factual_invention",
                        "diverse_candidates",
                    ],
                },
                "status": "draft",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM settings_versions WHERE id = CAST(:id AS uuid) AND status = 'draft'"
        ).bindparams(id=_SETTINGS_ID)
    )
    op.execute(
        sa.text(
            "DELETE FROM prompt_definitions WHERE id = CAST(:id AS uuid) AND status = 'draft'"
        ).bindparams(id=_PROMPT_ID)
    )
    op.execute(
        sa.text(
            "DELETE FROM recipe_definitions WHERE id = CAST(:id AS uuid) AND status = 'draft'"
        ).bindparams(id=_RECIPE_ID)
    )
    _drop_immutable_trigger(
        function_name="prevent_active_recipe_mutation",
        trigger_name="recipe_definitions_active_immutable",
        table_name="recipe_definitions",
    )
    _drop_immutable_trigger(
        function_name="prevent_active_prompt_mutation",
        trigger_name="prompt_definitions_active_immutable",
        table_name="prompt_definitions",
    )
    _drop_immutable_trigger(
        function_name="prevent_active_settings_version_mutation",
        trigger_name="settings_versions_active_immutable",
        table_name="settings_versions",
    )
    op.drop_index("uq_active_recipe_key", table_name="recipe_definitions")
    op.drop_index("uq_active_prompt_key", table_name="prompt_definitions")
    op.drop_index("uq_active_settings_system_scope", table_name="settings_versions")
    op.drop_index("uq_active_settings_project_scope", table_name="settings_versions")
    op.drop_column("model_calls", "runtime_metadata_json")
