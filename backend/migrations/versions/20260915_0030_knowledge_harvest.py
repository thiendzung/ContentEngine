"""Add immutable deterministic knowledge harvest snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0030"
down_revision: str | None = "20260915_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_harvest_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_knowledge_harvest() RETURNS trigger AS $$
            DECLARE
                case_project uuid;
                raw_topic_id text;
                topic_uuid uuid;
                topic_project uuid;
                topic_status text;
                topic_snapshot json;
                snapshot_topic_uuid uuid;
                snapshot_topic_project uuid;
                snapshot_topic_key text;
                snapshot_topic_name text;
                snapshot_topic_type text;
                snapshot_topic_description text;
                snapshot_topic_status text;
                snapshot_topic_metadata json;
                edge_snapshot json;
                snapshot_edge_uuid uuid;
                snapshot_edge_parent uuid;
                snapshot_edge_child uuid;
                snapshot_edge_project uuid;
                snapshot_edge_relation text;
                snapshot_edge_actor text;
                snapshot_edge_metadata json;
                item json;
                candidate_uuid uuid;
                candidate_project uuid;
                candidate_status text;
                candidate_locale text;
                candidate_statement text;
                candidate_summary text;
                candidate_hash text;
                candidate_reviewer text;
                candidate_review_reason text;
                candidate_entity_refs json;
                candidate_provenance json;
                scoped_link json;
                raw_link_id text;
                link_uuid uuid;
                raw_scoped_topic_id text;
                scoped_topic_uuid uuid;
                link_project uuid;
                link_topic uuid;
                link_candidate uuid;
                link_relevance integer;
                link_method_value text;
                link_actor text;
                link_metadata json;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'knowledge_harvest_is_immutable';
                END IF;

                IF NEW.content_case_id IS NOT NULL THEN
                    SELECT project_id INTO case_project
                    FROM content_cases WHERE id = NEW.content_case_id;
                    IF case_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_case_project_mismatch';
                    END IF;
                END IF;

                IF (
                    SELECT count(*)
                    FROM json_array_elements_text(NEW.requested_topic_ids_json)
                ) <> (
                    SELECT count(DISTINCT value)
                    FROM json_array_elements_text(NEW.requested_topic_ids_json)
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_requested_topic_duplicate';
                END IF;

                IF (
                    SELECT count(*)
                    FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                ) <> (
                    SELECT count(DISTINCT value)
                    FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_expanded_topic_duplicate';
                END IF;

                IF NEW.requested_topic_ids_json::jsonb IS DISTINCT FROM (
                    SELECT jsonb_agg(value ORDER BY value)
                    FROM jsonb_array_elements_text(NEW.requested_topic_ids_json::jsonb)
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_requested_topics_not_canonical';
                END IF;

                IF NEW.expanded_topic_ids_json::jsonb IS DISTINCT FROM (
                    SELECT jsonb_agg(value ORDER BY value)
                    FROM jsonb_array_elements_text(NEW.expanded_topic_ids_json::jsonb)
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_expanded_topics_not_canonical';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM json_array_elements_text(NEW.requested_topic_ids_json)
                        AS requested(value)
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                            AS expanded(value)
                        WHERE expanded.value = requested.value
                    )
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_requested_not_in_expanded';
                END IF;

                FOR raw_topic_id IN
                    SELECT value FROM json_array_elements_text(NEW.requested_topic_ids_json)
                LOOP
                    BEGIN
                        topic_uuid := raw_topic_id::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_invalid';
                    END;
                    IF raw_topic_id IS DISTINCT FROM topic_uuid::text THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_not_canonical';
                    END IF;
                    SELECT project_id, status INTO topic_project, topic_status
                    FROM topic_nodes WHERE id = topic_uuid;
                    IF topic_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_project_mismatch';
                    END IF;
                    IF topic_status <> 'active' THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_not_active';
                    END IF;
                END LOOP;

                FOR raw_topic_id IN
                    SELECT value FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                LOOP
                    BEGIN
                        topic_uuid := raw_topic_id::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_invalid';
                    END;
                    IF raw_topic_id IS DISTINCT FROM topic_uuid::text THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_not_canonical';
                    END IF;
                    SELECT project_id, status INTO topic_project, topic_status
                    FROM topic_nodes WHERE id = topic_uuid;
                    IF topic_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_project_mismatch';
                    END IF;
                    IF topic_status <> 'active' THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_not_active';
                    END IF;
                END LOOP;

                IF json_typeof(NEW.scope_graph_json) IS DISTINCT FROM 'object' THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_graph_invalid';
                END IF;
                IF (
                    SELECT array_agg(key ORDER BY key)
                    FROM json_object_keys(NEW.scope_graph_json) AS keys(key)
                ) IS DISTINCT FROM ARRAY['contains_edges', 'topics']::text[] THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_graph_shape_invalid';
                END IF;
                IF json_typeof(NEW.scope_graph_json->'topics') IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.scope_graph_json->'contains_edges')
                       IS DISTINCT FROM 'array' THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_graph_shape_invalid';
                END IF;

                IF json_array_length(NEW.scope_graph_json->'topics') < 1 THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_topics_required';
                END IF;
                IF json_array_length(NEW.scope_graph_json->'topics') IS DISTINCT FROM
                    json_array_length(NEW.expanded_topic_ids_json) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_topic_set_mismatch';
                END IF;
                IF (
                    SELECT count(*)
                    FROM json_array_elements(NEW.scope_graph_json->'topics')
                ) <> (
                    SELECT count(DISTINCT value->>'topic_id')
                    FROM json_array_elements(NEW.scope_graph_json->'topics')
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_topic_duplicate';
                END IF;
                IF (NEW.scope_graph_json->'topics')::jsonb IS DISTINCT FROM (
                    SELECT jsonb_agg(value ORDER BY value->>'topic_id')
                    FROM jsonb_array_elements(
                        (NEW.scope_graph_json->'topics')::jsonb
                    )
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_topics_not_canonical';
                END IF;

                FOR topic_snapshot IN
                    SELECT value FROM json_array_elements(NEW.scope_graph_json->'topics')
                LOOP
                    IF json_typeof(topic_snapshot) IS DISTINCT FROM 'object' THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_invalid';
                    END IF;
                    IF (
                        SELECT array_agg(key ORDER BY key)
                        FROM json_object_keys(topic_snapshot) AS keys(key)
                    ) IS DISTINCT FROM ARRAY[
                        'canonical_key',
                        'description',
                        'metadata',
                        'name',
                        'node_type',
                        'status',
                        'topic_id'
                    ]::text[] THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_shape_invalid';
                    END IF;
                    BEGIN
                        snapshot_topic_uuid := (topic_snapshot->>'topic_id')::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_id_invalid';
                    END;
                    IF topic_snapshot->>'topic_id'
                       IS DISTINCT FROM snapshot_topic_uuid::text THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_id_invalid';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                            AS expanded(value)
                        WHERE expanded.value = topic_snapshot->>'topic_id'
                    ) THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_outside_scope';
                    END IF;

                    SELECT
                        tn.project_id,
                        tn.canonical_key,
                        tn.name,
                        tn.node_type,
                        tn.description,
                        tn.status,
                        tn.metadata_json
                    INTO
                        snapshot_topic_project,
                        snapshot_topic_key,
                        snapshot_topic_name,
                        snapshot_topic_type,
                        snapshot_topic_description,
                        snapshot_topic_status,
                        snapshot_topic_metadata
                    FROM topic_nodes AS tn
                    WHERE tn.id = snapshot_topic_uuid;

                    IF snapshot_topic_project IS DISTINCT FROM NEW.project_id
                       OR snapshot_topic_status IS DISTINCT FROM 'active' THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_mismatch';
                    END IF;
                    IF topic_snapshot->>'canonical_key'
                           IS DISTINCT FROM snapshot_topic_key
                       OR topic_snapshot->>'name' IS DISTINCT FROM snapshot_topic_name
                       OR topic_snapshot->>'node_type' IS DISTINCT FROM snapshot_topic_type
                       OR topic_snapshot->>'description'
                           IS DISTINCT FROM snapshot_topic_description
                       OR topic_snapshot->>'status' IS DISTINCT FROM snapshot_topic_status
                       OR topic_snapshot->'metadata' IS NULL
                       OR (topic_snapshot->'metadata')::jsonb IS DISTINCT FROM
                           snapshot_topic_metadata::jsonb THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_topic_snapshot_mismatch';
                    END IF;
                END LOOP;

                IF (
                    SELECT count(*)
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                ) <> (
                    SELECT count(*)
                    FROM topic_edges AS te
                    WHERE te.project_id = NEW.project_id
                      AND te.relation_type = 'contains'
                      AND te.parent_topic_id IN (
                          SELECT value::uuid
                          FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                      )
                      AND te.child_topic_id IN (
                          SELECT value::uuid
                          FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                      )
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_edge_set_mismatch';
                END IF;
                IF (
                    SELECT count(*)
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                ) <> (
                    SELECT count(DISTINCT value->>'edge_id')
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_edge_duplicate';
                END IF;
                IF (
                    SELECT count(*)
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                ) <> (
                    SELECT count(
                        DISTINCT (value->>'parent_topic_id', value->>'child_topic_id')
                    )
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_edge_duplicate';
                END IF;
                IF json_array_length(NEW.scope_graph_json->'contains_edges') > 0
                   AND (NEW.scope_graph_json->'contains_edges')::jsonb
                       IS DISTINCT FROM (
                           SELECT jsonb_agg(
                               value ORDER BY
                                   value->>'parent_topic_id',
                                   value->>'child_topic_id',
                                   value->>'edge_id'
                           )
                           FROM jsonb_array_elements(
                               (NEW.scope_graph_json->'contains_edges')::jsonb
                           )
                       ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_scope_edges_not_canonical';
                END IF;

                FOR edge_snapshot IN
                    SELECT value
                    FROM json_array_elements(NEW.scope_graph_json->'contains_edges')
                LOOP
                    IF json_typeof(edge_snapshot) IS DISTINCT FROM 'object' THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_invalid';
                    END IF;
                    IF (
                        SELECT array_agg(key ORDER BY key)
                        FROM json_object_keys(edge_snapshot) AS keys(key)
                    ) IS DISTINCT FROM ARRAY[
                        'child_topic_id',
                        'created_by',
                        'edge_id',
                        'metadata',
                        'parent_topic_id',
                        'relation_type'
                    ]::text[] THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_shape_invalid';
                    END IF;
                    BEGIN
                        snapshot_edge_uuid := (edge_snapshot->>'edge_id')::uuid;
                        snapshot_edge_parent := (edge_snapshot->>'parent_topic_id')::uuid;
                        snapshot_edge_child := (edge_snapshot->>'child_topic_id')::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_id_invalid';
                    END;
                    IF edge_snapshot->>'edge_id'
                           IS DISTINCT FROM snapshot_edge_uuid::text
                       OR edge_snapshot->>'parent_topic_id'
                           IS DISTINCT FROM snapshot_edge_parent::text
                       OR edge_snapshot->>'child_topic_id'
                           IS DISTINCT FROM snapshot_edge_child::text THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_id_invalid';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                            AS expanded(value)
                        WHERE expanded.value = edge_snapshot->>'parent_topic_id'
                    ) OR NOT EXISTS (
                        SELECT 1
                        FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                            AS expanded(value)
                        WHERE expanded.value = edge_snapshot->>'child_topic_id'
                    ) THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_outside_scope';
                    END IF;

                    SELECT
                        te.project_id,
                        te.parent_topic_id,
                        te.child_topic_id,
                        te.relation_type,
                        te.created_by,
                        te.metadata_json
                    INTO
                        snapshot_edge_project,
                        snapshot_edge_parent,
                        snapshot_edge_child,
                        snapshot_edge_relation,
                        snapshot_edge_actor,
                        snapshot_edge_metadata
                    FROM topic_edges AS te
                    WHERE te.id = snapshot_edge_uuid;

                    IF snapshot_edge_project IS DISTINCT FROM NEW.project_id
                       OR snapshot_edge_relation IS DISTINCT FROM 'contains' THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_mismatch';
                    END IF;
                    IF edge_snapshot->>'parent_topic_id'
                           IS DISTINCT FROM snapshot_edge_parent::text
                       OR edge_snapshot->>'child_topic_id'
                           IS DISTINCT FROM snapshot_edge_child::text
                       OR edge_snapshot->>'relation_type'
                           IS DISTINCT FROM snapshot_edge_relation
                       OR edge_snapshot->>'created_by'
                           IS DISTINCT FROM snapshot_edge_actor
                       OR edge_snapshot->'metadata' IS NULL
                       OR (edge_snapshot->'metadata')::jsonb IS DISTINCT FROM
                           snapshot_edge_metadata::jsonb THEN
                        RAISE EXCEPTION 'knowledge_harvest_scope_edge_snapshot_mismatch';
                    END IF;
                END LOOP;

                FOR item IN SELECT value FROM json_array_elements(NEW.items_json)
                LOOP
                    IF item->>'candidate_id' IS NULL THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_id_required';
                    END IF;
                    BEGIN
                        candidate_uuid := (item->>'candidate_id')::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_id_invalid';
                    END;
                    IF item->>'candidate_id' IS DISTINCT FROM candidate_uuid::text THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_id_not_canonical';
                    END IF;

                    SELECT
                        project_id,
                        status,
                        locale,
                        statement,
                        summary,
                        provenance_json->>'candidate_content_hash',
                        reviewer,
                        review_reason,
                        entity_refs_json,
                        provenance_json
                    INTO
                        candidate_project,
                        candidate_status,
                        candidate_locale,
                        candidate_statement,
                        candidate_summary,
                        candidate_hash,
                        candidate_reviewer,
                        candidate_review_reason,
                        candidate_entity_refs,
                        candidate_provenance
                    FROM knowledge_candidates WHERE id = candidate_uuid;

                    IF candidate_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_project_mismatch';
                    END IF;
                    IF candidate_status <> 'APPROVED' THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_not_approved';
                    END IF;
                    IF candidate_locale IS DISTINCT FROM NEW.locale THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_locale_mismatch';
                    END IF;
                    IF item->>'locale' IS DISTINCT FROM NEW.locale THEN
                        RAISE EXCEPTION 'knowledge_harvest_item_locale_mismatch';
                    END IF;
                    IF item->>'statement' IS DISTINCT FROM candidate_statement
                       OR item->>'summary' IS DISTINCT FROM candidate_summary THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_text_mismatch';
                    END IF;
                    IF item->>'candidate_content_hash' IS DISTINCT FROM candidate_hash THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_hash_mismatch';
                    END IF;
                    IF item->'entity_refs' IS NULL
                       OR (item->'entity_refs')::jsonb IS DISTINCT FROM
                           candidate_entity_refs::jsonb THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_entity_refs_mismatch';
                    END IF;
                    IF item#>>'{admission,status}' IS DISTINCT FROM 'APPROVED'
                       OR item#>>'{admission,reviewer}' IS DISTINCT FROM candidate_reviewer
                       OR item#>>'{admission,review_reason}' IS DISTINCT FROM
                           candidate_review_reason THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_admission_mismatch';
                    END IF;
                    IF item->'lineage' IS NULL OR (item->'lineage')::jsonb IS DISTINCT FROM
                        jsonb_build_object(
                            'evidence_set', candidate_provenance::jsonb->'evidence_set',
                            'claim_id', candidate_provenance::jsonb->'claim_id',
                            'evidence_ids', candidate_provenance::jsonb->'evidence_ids',
                            'source_document_ids',
                                candidate_provenance::jsonb->'source_document_ids',
                            'source_ids', candidate_provenance::jsonb->'source_ids',
                            'relation_counts', candidate_provenance::jsonb->'relation_counts',
                            'evidence_refs', candidate_provenance::jsonb->'evidence_refs'
                        ) THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_lineage_mismatch';
                    END IF;
                    IF item#>>'{freshness,state}' IS NULL OR item#>>'{freshness,state}' NOT IN
                        ('FRESH','DUE','STALE','UNKNOWN','UNCLASSIFIED') THEN
                        RAISE EXCEPTION 'knowledge_harvest_freshness_state_invalid';
                    END IF;
                    IF json_typeof(item->'scoped_topic_links') IS DISTINCT FROM 'array'
                       OR json_array_length(item->'scoped_topic_links') = 0 THEN
                        RAISE EXCEPTION 'knowledge_harvest_scoped_topic_links_required';
                    END IF;
                    IF (
                        SELECT count(*) FROM json_array_elements(item->'scoped_topic_links')
                    ) <> (
                        SELECT count(DISTINCT value->>'topic_id')
                        FROM json_array_elements(item->'scoped_topic_links')
                    ) THEN
                        RAISE EXCEPTION 'knowledge_harvest_scoped_topic_duplicate';
                    END IF;

                    FOR scoped_link IN
                        SELECT value FROM json_array_elements(item->'scoped_topic_links')
                    LOOP
                        raw_link_id := scoped_link->>'link_id';
                        raw_scoped_topic_id := scoped_link->>'topic_id';
                        IF raw_link_id IS NULL OR raw_scoped_topic_id IS NULL THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_link_invalid';
                        END IF;
                        BEGIN
                            link_uuid := raw_link_id::uuid;
                            scoped_topic_uuid := raw_scoped_topic_id::uuid;
                        EXCEPTION WHEN invalid_text_representation THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_link_invalid';
                        END;
                        IF raw_link_id IS DISTINCT FROM link_uuid::text
                           OR raw_scoped_topic_id IS DISTINCT FROM scoped_topic_uuid::text THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_link_not_canonical';
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1
                            FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                                AS expanded(value)
                            WHERE expanded.value = raw_scoped_topic_id
                        ) THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_outside_scope';
                        END IF;

                        SELECT
                            ktl.project_id,
                            ktl.topic_id,
                            ktl.knowledge_candidate_id,
                            ktl.relevance_score,
                            ktl.link_method,
                            ktl.linked_by,
                            ktl.metadata_json
                        INTO
                            link_project,
                            link_topic,
                            link_candidate,
                            link_relevance,
                            link_method_value,
                            link_actor,
                            link_metadata
                        FROM knowledge_topic_links AS ktl
                        WHERE ktl.id = link_uuid;

                        IF link_project IS DISTINCT FROM NEW.project_id
                           OR link_topic IS DISTINCT FROM scoped_topic_uuid
                           OR link_candidate IS DISTINCT FROM candidate_uuid THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_link_mismatch';
                        END IF;
                        IF (scoped_link->>'relevance_score')::integer IS DISTINCT FROM
                               link_relevance
                           OR scoped_link->>'link_method' IS DISTINCT FROM link_method_value
                           OR scoped_link->>'linked_by' IS DISTINCT FROM link_actor
                           OR scoped_link->'metadata' IS NULL
                           OR (scoped_link->'metadata')::jsonb IS DISTINCT FROM
                               link_metadata::jsonb THEN
                            RAISE EXCEPTION 'knowledge_harvest_scoped_topic_link_snapshot_mismatch';
                        END IF;
                    END LOOP;
                END LOOP;

                IF json_array_length(NEW.items_json) > 0 AND (
                    NEW.items_json::jsonb IS DISTINCT FROM (
                        SELECT jsonb_agg(value ORDER BY value->>'candidate_id')
                        FROM jsonb_array_elements(NEW.items_json::jsonb)
                    )
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_items_not_canonical';
                END IF;

                IF (
                    SELECT count(*) FROM json_array_elements(NEW.items_json)
                ) <> (
                    SELECT count(DISTINCT value->>'candidate_id')
                    FROM json_array_elements(NEW.items_json)
                ) THEN
                    RAISE EXCEPTION 'knowledge_harvest_candidate_duplicate';
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
            CREATE TRIGGER knowledge_harvests_guard
            BEFORE INSERT OR UPDATE OR DELETE ON knowledge_harvests
            FOR EACH ROW EXECUTE FUNCTION validate_knowledge_harvest()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_harvests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_topic_ids_json", sa.JSON(), nullable=False),
        sa.Column("expanded_topic_ids_json", sa.JSON(), nullable=False),
        sa.Column("scope_graph_json", sa.JSON(), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("harvest_method", sa.String(length=64), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_harvests_locale_required",
        ),
        sa.CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_harvests_created_by_required",
        ),
        sa.CheckConstraint(
            "harvest_method = 'approved_candidate_topic_scope_v1'",
            name="ck_knowledge_harvests_method",
        ),
        sa.CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_harvests_hash",
        ),
        sa.CheckConstraint(
            "json_array_length(requested_topic_ids_json) > 0",
            name="ck_knowledge_harvests_requested_topics",
        ),
        sa.CheckConstraint(
            "json_array_length(expanded_topic_ids_json) > 0",
            name="ck_knowledge_harvests_expanded_topics",
        ),
        sa.CheckConstraint(
            "json_typeof(scope_graph_json) = 'object'",
            name="ck_knowledge_harvests_scope_graph_object",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_harvests_project_hash",
        "knowledge_harvests",
        ["project_id", "snapshot_hash"],
        unique=True,
    )
    op.create_index(
        "ix_knowledge_harvests_project_locale_time",
        "knowledge_harvests",
        ["project_id", "locale", "as_of"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_harvests_case",
        "knowledge_harvests",
        ["content_case_id"],
        unique=False,
    )
    _create_harvest_guard()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS knowledge_harvests_guard ON knowledge_harvests"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_knowledge_harvest()"))
    op.drop_index("ix_knowledge_harvests_case", table_name="knowledge_harvests")
    op.drop_index(
        "ix_knowledge_harvests_project_locale_time",
        table_name="knowledge_harvests",
    )
    op.drop_index(
        "uq_knowledge_harvests_project_hash",
        table_name="knowledge_harvests",
    )
    op.drop_table("knowledge_harvests")
