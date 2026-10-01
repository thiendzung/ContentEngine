from uuid import uuid4

from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderCallArtifact,
    SourceCandidate,
)
from app.modules.research.evidence.artifact import (
    evidence_workflow_payload,
    research_failure_diagnostic_payload,
)
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


def test_research_failure_diagnostic_strips_url_query_and_fragment() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url="https://user:SECRET_PASSWORD@example.test/source?token=SECRET_TOKEN&session=abc#private",
        title="Evidence source",
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        why_selected="Controlled source.",
        parent_url="https://parent.test/path?signed=SECRET_PARENT#fragment",
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art authenticity",
            max_pages_to_read=1,
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        ),
        source_candidates=[candidate],
        selected_sources=[candidate],
        documents=[
            PageDocument(
                provider="jina",
                url=candidate.url,
                requested_url=(
                    "https://example.test/source?token=SECRET_REQUEST#fragment"
                ),
                final_url="https://example.test/final?token=SECRET_FINAL#fragment",
                content="Page content must not appear in the diagnostic.",
            )
        ],
        stop_reason="controlled",
        sufficient=False,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        relation_counts={"supports": 1},
        research_gaps=["Controlled unresolved gap."],
        evidence_eligible=True,
    )

    payload = research_failure_diagnostic_payload(result)
    serialized = str(payload)

    assert "SECRET_PASSWORD" not in serialized
    assert "SECRET_TOKEN" not in serialized
    assert "SECRET_PARENT" not in serialized
    assert "SECRET_REQUEST" not in serialized
    assert "SECRET_FINAL" not in serialized
    research = payload["research"]
    assert isinstance(research, dict)
    sources = research["selected_sources"]
    assert isinstance(sources, list)
    assert sources[0]["url"] == "https://example.test/source"
    assert sources[0]["parent_url"] == "https://parent.test/path"
    documents = research["read_documents"]
    assert isinstance(documents, list)
    assert documents[0]["requested_url"] == "https://example.test/source"
    assert documents[0]["final_url"] == "https://example.test/final"


