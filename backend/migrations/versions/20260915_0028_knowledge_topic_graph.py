"""Add durable project-scoped knowledge topic graph."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0028"
down_revision: str | None = "20260914_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_topic_scope_triggers() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_topic_edge_scope() RETURNS trigger AS $$
            DECLARE
                parent_project uuid;
                child_project uuid;
                parent_status text;
                child_status text;
                parent_rank integer;
                child_rank integer;
            BEGIN
                SELECT project_id, status,
                    CASE node_type
                        WHEN 'pillar' THEN 0
                        WHEN 'cluster' THEN 1
                        WHEN 'topic' THEN 2
                        WHEN 'subtopic' THEN 3
                    END
                INTO parent_project, parent_status, parent_rank
                FROM topic_nodes WHERE id = NEW.parent_topic_id;

                SELECT project_id, status,
                    CASE node_type
                        WHEN 'pillar' THEN 0
                        WHEN 'cluster' THEN 1
                        WHEN 'topic' THEN 2
                        WHEN 'subtopic' THEN 3
                    END
                INTO child_project, child_status, child_rank
                FROM topic_nodes WHERE id = NEW.child_topic_id;

                IF parent_project IS DISTINCT FROM NEW.project_id
                    OR child_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'topic_edge_project_mismatch';
                END IF;
                IF parent_status <> 'active' OR child_status <> 'active' THEN
                    RAISE EXCEPTION 'topic_edge_requires_active_topics';
                END IF;
                IF NEW.relation_type = 'contains' AND parent_rank >= child_rank THEN
                    RAISE EXCEPTION 'topic_contains_hierarchy_invalid';
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
            CREATE TRIGGER topic_edges_scope_guard
            BEFORE INSERT OR UPDATE ON topic_edges
            FOR EACH ROW EXECUTE FUNCTION validate_topic_edge_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_knowledge_topic_link_scope() RETURNS trigger AS $$
            DECLARE
                topic_project uuid;
                topic_status text;
                target_project uuid;
            BEGIN
                SELECT project_id, status INTO topic_project, topic_status
                FROM topic_nodes WHERE id = NEW.topic_id;

                IF topic_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'topic_link_project_mismatch';
                END IF;
                IF topic_status <> 'active' THEN
                    RAISE EXCEPTION 'topic_link_requires_active_topic';
                END IF;

                IF NEW.claim_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM claims WHERE id = NEW.claim_id;
                ELSIF NEW.knowledge_candidate_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM knowledge_candidates WHERE id = NEW.knowledge_candidate_id;
                ELSIF NEW.entity_id IS NOT NULL THEN
                    SELECT project_id INTO target_project
                    FROM entities WHERE id = NEW.entity_id;
                ELSIF NEW.chunk_id IS NOT NULL THEN
                    SELECT s.project_id INTO target_project
                    FROM knowledge_chunks kc
                    JOIN source_documents sd ON sd.id = kc.source_document_id
                    JOIN sources s ON s.id = sd.source_id
                    WHERE kc.id = NEW.chunk_id;
                END IF;

                IF target_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'topic_link_target_project_mismatch';
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
            CREATE TRIGGER knowledge_topic_links_scope_guard
            BEFORE INSERT OR UPDATE ON knowledge_topic_links
            FOR EACH ROW EXECUTE FUNCTION validate_knowledge_topic_link_scope()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "topic_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("node_type", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "node_type in ('pillar','cluster','topic','subtopic')",
            name="ck_topic_nodes_type",
        ),
        sa.CheckConstraint(
            "status in ('active','retired')",
            name="ck_topic_nodes_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_topic_nodes_project_key",
        "topic_nodes",
        ["project_id", "canonical_key"],
        unique=True,
    )
    op.create_index(
        "ix_topic_nodes_project_type",
        "topic_nodes",
        ["project_id", "node_type", "status"],
        unique=False,
    )

    op.create_table(
        "topic_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_topic_id", sa.Uuid(), nullable=False),
        sa.Column("child_topic_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "relation_type in ('contains','related')",
            name="ck_topic_edges_relation_type",
        ),
        sa.CheckConstraint(
            "parent_topic_id <> child_topic_id",
            name="ck_topic_edges_not_self",
        ),
        sa.CheckConstraint(
            "relation_type <> 'related' OR parent_topic_id < child_topic_id",
            name="ck_topic_edges_related_canonical_order",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["parent_topic_id"], ["topic_nodes.id"]),
        sa.ForeignKeyConstraint(["child_topic_id"], ["topic_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_topic_edges_exact",
        "topic_edges",
        ["project_id", "parent_topic_id", "child_topic_id", "relation_type"],
        unique=True,
    )
    op.create_index(
        "ix_topic_edges_parent",
        "topic_edges",
        ["project_id", "parent_topic_id", "relation_type"],
        unique=False,
    )
    op.create_index(
        "ix_topic_edges_child",
        "topic_edges",
        ["project_id", "child_topic_id", "relation_type"],
        unique=False,
    )

    op.create_table(
        "knowledge_topic_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("link_method", sa.String(length=32), nullable=False),
        sa.Column("linked_by", sa.String(length=200), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN chunk_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_knowledge_topic_links_exactly_one_target",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 and relevance_score <= 1000",
            name="ck_knowledge_topic_links_relevance",
        ),
        sa.CheckConstraint(
            "link_method in ('manual','deterministic','model')",
            name="ck_knowledge_topic_links_method",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["topic_nodes.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(
            ["knowledge_candidate_id"],
            ["knowledge_candidates.id"],
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_topic_links_claim",
        "knowledge_topic_links",
        ["topic_id", "claim_id"],
        unique=True,
        postgresql_where=sa.text("claim_id IS NOT NULL"),
    )
    op.create_index(
        "uq_knowledge_topic_links_candidate",
        "knowledge_topic_links",
        ["topic_id", "knowledge_candidate_id"],
        unique=True,
        postgresql_where=sa.text("knowledge_candidate_id IS NOT NULL"),
    )
    op.create_index(
        "uq_knowledge_topic_links_chunk",
        "knowledge_topic_links",
        ["topic_id", "chunk_id"],
        unique=True,
        postgresql_where=sa.text("chunk_id IS NOT NULL"),
    )
    op.create_index(
        "uq_knowledge_topic_links_entity",
        "knowledge_topic_links",
        ["topic_id", "entity_id"],
        unique=True,
        postgresql_where=sa.text("entity_id IS NOT NULL"),
    )
    op.create_index(
        "ix_knowledge_topic_links_project_topic",
        "knowledge_topic_links",
        ["project_id", "topic_id"],
        unique=False,
    )
    _create_topic_scope_triggers()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS knowledge_topic_links_scope_guard "
            "ON knowledge_topic_links"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_knowledge_topic_link_scope()"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS topic_edges_scope_guard ON topic_edges"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_topic_edge_scope()"))

    op.drop_index(
        "ix_knowledge_topic_links_project_topic",
        table_name="knowledge_topic_links",
    )
    op.drop_index(
        "uq_knowledge_topic_links_entity",
        table_name="knowledge_topic_links",
    )
    op.drop_index(
        "uq_knowledge_topic_links_chunk",
        table_name="knowledge_topic_links",
    )
    op.drop_index(
        "uq_knowledge_topic_links_candidate",
        table_name="knowledge_topic_links",
    )
    op.drop_index(
        "uq_knowledge_topic_links_claim",
        table_name="knowledge_topic_links",
    )
    op.drop_table("knowledge_topic_links")

    op.drop_index("ix_topic_edges_child", table_name="topic_edges")
    op.drop_index("ix_topic_edges_parent", table_name="topic_edges")
    op.drop_index("uq_topic_edges_exact", table_name="topic_edges")
    op.drop_table("topic_edges")

    op.drop_index("ix_topic_nodes_project_type", table_name="topic_nodes")
    op.drop_index("uq_topic_nodes_project_key", table_name="topic_nodes")
    op.drop_table("topic_nodes")
