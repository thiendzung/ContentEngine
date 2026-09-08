from uuid import uuid4

from app.modules.research.contracts import (
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderCallArtifact,
)
from app.modules.research.evidence.artifact import evidence_workflow_payload
from app.modules.research.evidence.contracts import EvidenceResearchResult


def test_evidence_artifact_keeps_refs_without_raw_provider_or_page_content() -> None:
    project_id = uuid4()
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art price",
            max_pages_to_read=1,
        ),
        calls=[
            ProviderCallArtifact(
                provider="serper",
                operation="search",
                query="art price",
                purpose="test",
                status="ok",
                result_count=1,
                raw_excerpt="RAW_PROVIDER_PAYLOAD_MUST_NOT_APPEAR",
            )
        ],
        documents=[
            PageDocument(
                provider="jina",
                url="https://example.test/source",
                content="FULL_PAGE_CONTENT_MUST_NOT_APPEAR",
            )
        ],
        stop_reason="serper_sufficient",
        sufficient=True,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        source_document_ids=[uuid4()],
        claim_ids=[uuid4()],
        evidence_ids=[uuid4()],
        relation_counts={"supports": 1},
        evidence_set_id=uuid4(),
        evidence_set_version=1,
        evidence_set_status="draft",
        originality_pack_id=uuid4(),
        research_gaps=[],
        evidence_eligible=True,
    )

    payload = evidence_workflow_payload(result)
    serialized = str(payload)

    assert "RAW_PROVIDER_PAYLOAD_MUST_NOT_APPEAR" not in serialized
    assert "FULL_PAGE_CONTENT_MUST_NOT_APPEAR" not in serialized
    assert payload["evidence_eligible"] is True
    assert payload["evidence_ids"] == [str(result.evidence_ids[0])]
