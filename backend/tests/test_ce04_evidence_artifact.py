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


def test_research_failure_diagnostic_strips_url_query_fragment_and_userinfo() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url=(
            "https://user:SECRET_PASSWORD@example.test/source"
            "?token=SECRET_TOKEN&session=abc#private"
        ),
        title="Evidence source",
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        why_selected="Controlled source.",
        parent_url="//user:SECRET_PARENT@example.test/parent?signed=token#fragment",
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
    assert str(sources[0]["url"]).startswith("url-sha256:")
    assert str(sources[0]["parent_url"]).startswith("url-sha256:")
    documents = research["read_documents"]
    assert isinstance(documents, list)
    assert str(documents[0]["requested_url"]).startswith("url-sha256:")
    assert str(documents[0]["final_url"]).startswith("url-sha256:")
    assert "example.test" not in serialized


def test_research_failure_diagnostic_fingerprints_raw_url_path() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url=(
            "https://example.test/app;jsessionid=SECRET_PATH/page"
            "?token=SECRET_QUERY#fragment"
        ),
        title="Credential-bearing path",
        source_type="unknown",
        commercial_bias=CommercialBias.UNKNOWN,
        intended_use=IntendedUse.DISCOVERY,
        why_selected="Unselected credential-bearing candidate.",
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art authenticity",
            max_pages_to_read=1,
        ),
        source_candidates=[candidate],
        stop_reason="controlled",
        sufficient=False,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        relation_counts={},
        research_gaps=["Controlled unresolved gap."],
        evidence_eligible=False,
    )

    payload = research_failure_diagnostic_payload(result)
    research = payload["research"]
    assert isinstance(research, dict)
    candidates = research["source_candidates"]
    assert isinstance(candidates, list) and candidates
    url = candidates[0]["url"]
    assert isinstance(url, str)
    assert url.startswith("url-sha256:")
    serialized = str(payload)
    assert "SECRET_PATH" not in serialized
    assert "SECRET_QUERY" not in serialized
    assert "jsessionid" not in serialized.casefold()
    assert "/app;" not in serialized
    assert "example.test" not in serialized


def test_research_failure_diagnostic_fingerprints_encoded_authority() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url=(
            "https://user%3ASECRET_AUTHORITY%40example.test/path"
            "?token=SECRET_QUERY#fragment"
        ),
        title="Encoded authority provider result",
        source_type="unknown",
        commercial_bias=CommercialBias.UNKNOWN,
        intended_use=IntendedUse.DISCOVERY,
        why_selected="Unselected encoded-authority candidate.",
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art authenticity",
            max_pages_to_read=1,
        ),
        source_candidates=[candidate],
        stop_reason="controlled",
        sufficient=False,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        relation_counts={},
        research_gaps=["Controlled unresolved gap."],
        evidence_eligible=False,
    )

    payload = research_failure_diagnostic_payload(result)
    research = payload["research"]
    assert isinstance(research, dict)
    candidates = research["source_candidates"]
    assert isinstance(candidates, list) and candidates
    url = candidates[0]["url"]
    assert isinstance(url, str)
    assert url.startswith("url-sha256:")
    serialized = str(payload)
    assert "SECRET_AUTHORITY" not in serialized
    assert "SECRET_QUERY" not in serialized
    assert "%3A" not in serialized
    assert "%40" not in serialized


def test_research_failure_diagnostic_fingerprints_authorityless_url() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url="https:user:SECRET_AUTHORITYLESS@example.test/path?token=x#fragment",
        title="Authority-less provider result",
        source_type="unknown",
        commercial_bias=CommercialBias.UNKNOWN,
        intended_use=IntendedUse.DISCOVERY,
        why_selected="Unselected authority-less candidate.",
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art authenticity",
            max_pages_to_read=1,
        ),
        source_candidates=[candidate],
        stop_reason="controlled",
        sufficient=False,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        relation_counts={},
        research_gaps=["Controlled unresolved gap."],
        evidence_eligible=False,
    )

    payload = research_failure_diagnostic_payload(result)
    research = payload["research"]
    assert isinstance(research, dict)
    candidates = research["source_candidates"]
    assert isinstance(candidates, list) and candidates
    url = candidates[0]["url"]
    assert isinstance(url, str)
    assert url.startswith("url-sha256:")
    serialized = str(payload)
    assert "SECRET_AUTHORITYLESS" not in serialized
    assert "https:user:" not in serialized


def test_research_failure_diagnostic_tolerates_malformed_provider_url() -> None:
    project_id = uuid4()
    candidate = SourceCandidate(
        provider="exa",
        query="art authenticity",
        url="http://[bad",
        title="Malformed provider result",
        source_type="unknown",
        commercial_bias=CommercialBias.UNKNOWN,
        intended_use=IntendedUse.DISCOVERY,
        why_selected="Unselected malformed candidate.",
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=project_id,
            query="art authenticity",
            max_pages_to_read=1,
        ),
        source_candidates=[candidate],
        stop_reason="controlled",
        sufficient=False,
    )
    result = EvidenceResearchResult(
        research=production,
        content_case_id=uuid4(),
        relation_counts={},
        research_gaps=["Controlled unresolved gap."],
        evidence_eligible=False,
    )

    payload = research_failure_diagnostic_payload(result)
    research = payload["research"]
    assert isinstance(research, dict)
    candidates = research["source_candidates"]
    assert isinstance(candidates, list) and candidates
    url = candidates[0]["url"]
    assert isinstance(url, str)
    assert url.startswith("url-sha256:")
    assert "http://[bad" not in str(payload)
