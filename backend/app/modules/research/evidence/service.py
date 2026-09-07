from __future__ import annotations

import re
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.ingest import canonicalize_markdown
from app.modules.research.contracts import ProductionResearchRequest, ProductionResearchResult
from app.modules.research.evidence.artifact import persist_evidence_artifact
from app.modules.research.evidence.contracts import (
    ClaimCandidate,
    EvidenceRelation,
    EvidenceResearchRequest,
    EvidenceResearchResult,
)
from app.modules.research.evidence.persistence import (
    build_originality_pack,
    create_or_reuse_evidence_set,
    ensure_selected_content_case,
    lock_evidence_set,
    persist_claim_evidence,
    persist_read_documents,
)


class ProductionResearchRunner(Protocol):
    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult: ...


_STOPWORDS = {
    "about",
    "after",
    "before",
    "between",
    "could",
    "from",
    "have",
    "into",
    "original",
    "should",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


class EvidenceResearchWorkflow:
    """Turn a selected opportunity into traceable Claim/Evidence records."""

    def __init__(self, *, router: ProductionResearchRunner) -> None:
        self._router = router

    async def run(
        self,
        session: AsyncSession,
        *,
        request: EvidenceResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> EvidenceResearchResult:
        self._validate_request(request, run_id=run_id, step_run_id=step_run_id)
        content_case, opportunity, hypothesis = await ensure_selected_content_case(
            session,
            project_id=request.research.project_id,
            content_opportunity_id=request.content_opportunity_id,
            need_hypothesis_id=request.need_hypothesis_id,
        )
        if hypothesis.status != "PROPOSED":
            raise ValueError("pr_e_need_hypothesis_must_remain_proposed")

        production = await self._router.run(
            session,
            request=request.research,
            run_id=run_id,
            step_run_id=step_run_id,
        )
        page_refs = await persist_read_documents(session, production=production)

        explicit = list(request.explicit_candidates)
        automatic = self._extract_claim_candidates(
            production,
            topic_texts=(
                opportunity.question,
                opportunity.need,
                opportunity.promise,
            ),
            limit=request.max_claims,
        )
        candidates = self._merge_candidates(
            explicit,
            automatic,
            limit=request.max_claims,
        )

        links = []
        for candidate in candidates:
            links.append(
                await persist_claim_evidence(
                    session,
                    project_id=request.research.project_id,
                    page_refs=page_refs,
                    candidate=candidate,
                )
            )

        claim_ids = list(dict.fromkeys(link.claim_id for link in links))
        evidence_ids = list(dict.fromkeys(link.evidence_id for link in links))
        relation_counts = {relation.value: 0 for relation in EvidenceRelation}
        for link in links:
            relation_counts[link.relation.value] += 1

        evidence_set = None
        if evidence_ids:
            evidence_set = await create_or_reuse_evidence_set(
                session,
                project_id=request.research.project_id,
                content_case_id=content_case.id,
                evidence_ids=evidence_ids,
            )
            if request.lock_evidence_set:
                assert request.locked_by is not None
                evidence_set = await lock_evidence_set(
                    session,
                    evidence_set_id=evidence_set.id,
                    locked_by=request.locked_by,
                )

        originality = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=list(opportunity.motgu_material_refs_json),
        )
        gaps = self._research_gaps(
            production=production,
            evidence_count=len(evidence_ids),
            relation_counts=relation_counts,
            originality_item_count=len(originality.item_refs_json),
        )
        result = EvidenceResearchResult(
            research=production,
            content_case_id=content_case.id,
            source_document_ids=list(
                dict.fromkeys(ref.source_document_id for ref in page_refs.values())
            ),
            claim_ids=claim_ids,
            evidence_ids=evidence_ids,
            relation_counts=relation_counts,
            evidence_set_id=evidence_set.id if evidence_set is not None else None,
            evidence_set_version=(
                evidence_set.version if evidence_set is not None else None
            ),
            evidence_set_status=(
                evidence_set.status if evidence_set is not None else None
            ),
            originality_pack_id=originality.id,
            originality_item_count=len(originality.item_refs_json),
            research_gaps=gaps,
            evidence_eligible=bool(evidence_ids),
        )
        if run_id is not None and step_run_id is not None:
            artifact = await persist_evidence_artifact(
                session,
                run_id=run_id,
                step_run_id=step_run_id,
                result=result,
            )
            result.artifact_ref = str(artifact.id)
        return result

    def _validate_request(
        self,
        request: EvidenceResearchRequest,
        *,
        run_id: UUID | None,
        step_run_id: UUID | None,
    ) -> None:
        if request.max_claims < 1 or request.max_claims > 50:
            raise ValueError("max_claims_must_be_between_1_and_50")
        if len(request.explicit_candidates) > request.max_claims:
            raise ValueError("explicit_candidates_exceed_max_claims")
        if request.research.max_pages_to_read < 1:
            raise ValueError("evidence_research_requires_at_least_one_page_read")
        if (run_id is None) != (step_run_id is None):
            raise ValueError("run_id_and_step_run_id_must_be_provided_together")
        if request.lock_evidence_set and not (request.locked_by or "").strip():
            raise ValueError("locked_by_required_when_locking_evidence_set")

    def _extract_claim_candidates(
        self,
        production: ProductionResearchResult,
        *,
        topic_texts: tuple[str, ...],
        limit: int,
    ) -> list[ClaimCandidate]:
        terms = self._topic_terms(topic_texts)
        output: list[ClaimCandidate] = []
        seen: set[str] = set()

        for document in production.documents:
            source_url = document.final_url or document.url or document.requested_url
            if not source_url:
                continue
            canonical = canonicalize_markdown(document.content)
            segments = re.split(r"(?<=[.!;])(?:\s+|\n+)|\n{2,}", canonical)
            for index, raw_segment in enumerate(segments, start=1):
                excerpt = re.sub(
                    r"^(?:#{1,6}\s+|[-*+]\s+|>\s+)",
                    "",
                    raw_segment.strip(),
                ).strip()
                if not self._usable_statement(excerpt, terms):
                    continue
                fingerprint = self._normalize(excerpt)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                output.append(
                    ClaimCandidate(
                        statement=excerpt,
                        source_url=source_url,
                        locator=f"document_sentence:{index}",
                        excerpt=excerpt,
                        relation=EvidenceRelation.SUPPORTS,
                    )
                )
                if len(output) >= limit:
                    return output
        return output

    def _merge_candidates(
        self,
        explicit: list[ClaimCandidate],
        automatic: list[ClaimCandidate],
        *,
        limit: int,
    ) -> list[ClaimCandidate]:
        output: list[ClaimCandidate] = []
        seen: set[tuple[str, str, str]] = set()
        for candidate in (*explicit, *automatic):
            key = (
                self._normalize(candidate.statement),
                candidate.source_url.strip().casefold(),
                candidate.relation.value,
            )
            if key in seen:
                continue
            seen.add(key)
            output.append(candidate)
            if len(output) >= limit:
                break
        return output

    def _topic_terms(self, values: tuple[str, ...]) -> set[str]:
        terms: set[str] = set()
        for value in values:
            for token in re.findall(r"[a-z0-9]+", value.casefold()):
                if token in _STOPWORDS:
                    continue
                if len(token) >= 4 or token in {"art", "buy"}:
                    terms.add(token)
        return terms

    def _usable_statement(self, statement: str, terms: set[str]) -> bool:
        if len(statement) < 40 or len(statement) > 600:
            return False
        if statement.endswith("?"):
            return False
        normalized = self._normalize(statement)
        if normalized.startswith(("http://", "https://")):
            return False
        if not terms:
            return True
        statement_terms = set(re.findall(r"[a-z0-9]+", normalized))
        return bool(statement_terms.intersection(terms))

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    def _research_gaps(
        self,
        *,
        production: ProductionResearchResult,
        evidence_count: int,
        relation_counts: dict[str, int],
        originality_item_count: int,
    ) -> list[str]:
        gaps: list[str] = []
        if not production.sufficient:
            gaps.append(
                "Bounded research did not meet the production sufficiency policy: "
                f"{production.stop_reason}."
            )
        if not production.documents:
            gaps.append(
                "No external page was read successfully; SEARCH snippets remain ineligible "
                "for factual Evidence."
            )
        if evidence_count == 0:
            gaps.append("No source-backed Claim/Evidence link was created.")
        if relation_counts[EvidenceRelation.CONTRADICTS.value] == 0:
            gaps.append(
                "Contradiction coverage is still missing; absence of contradiction is not "
                "evidence of agreement."
            )
        if originality_item_count == 0:
            gaps.append(
                "Originality gap remains: no approved MOTGU-owned material reference is "
                "attached to this opportunity."
            )
        if any(document.content_truncated for document in production.documents):
            gaps.append("At least one evidence source was truncated during page reading.")
        return gaps
