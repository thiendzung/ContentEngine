from __future__ import annotations

import re
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.ingest import canonicalize_markdown
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    ProductionResearchRequest,
    ProductionResearchResult,
    SourceCandidate,
)
from app.modules.research.evidence.artifact import persist_evidence_artifact
from app.modules.research.evidence.contracts import (
    ClaimCandidate,
    EvidenceRelation,
    EvidenceResearchRequest,
    EvidenceResearchResult,
    count_usable_originality_items,
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
_SUBJECT_GENERIC_TERMS = {
    "appraisal",
    "appraise",
    "appraised",
    "evaluate",
    "evaluation",
    "fair",
    "fairly",
    "help",
    "know",
    "price",
    "priced",
    "pricing",
    "understand",
    "valuation",
    "value",
}
_SUBJECT_SYNONYMS = {
    "artwork": {"artwork", "artworks", "artist", "artists", "painting", "paintings"},
    "artworks": {"artwork", "artworks", "artist", "artists", "painting", "paintings"},
}
_MARKDOWN_LINK_ONLY_RE = re.compile(r"^\[[^\]]+\]\(https?://[^)]+\)$")
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")


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
            subject_text=hypothesis.statement,
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
                    approval_id=request.evidence_set_approval_id,
                )

        originality = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=list(opportunity.motgu_material_refs_json),
        )
        usable_originality_item_count = count_usable_originality_items(
            originality.item_refs_json
        )
        gaps = self._research_gaps(
            production=production,
            evidence_count=len(evidence_ids),
            relation_counts=relation_counts,
            originality_item_count=usable_originality_item_count,
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
            evidence_set_content_hash=(
                evidence_set.content_hash if evidence_set is not None else None
            ),
            evidence_set_status=(
                evidence_set.status if evidence_set is not None else None
            ),
            originality_pack_id=originality.id,
            originality_item_count=usable_originality_item_count,
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
        if request.lock_evidence_set:
            if not (request.locked_by or "").strip():
                raise ValueError("locked_by_required_when_locking_evidence_set")
            if request.evidence_set_approval_id is None:
                raise ValueError("evidence_set_approval_required_when_locking_evidence_set")

    def _extract_claim_candidates(
        self,
        production: ProductionResearchResult,
        *,
        subject_text: str,
        topic_texts: tuple[str, ...],
        limit: int,
    ) -> list[ClaimCandidate]:
        terms = self._topic_terms((*topic_texts, production.request.query))
        subject_terms = self._subject_terms(subject_text)
        sources = self._source_candidates_by_url(production)
        buckets: list[list[ClaimCandidate]] = []

        for document in production.documents:
            source_url = document.final_url or document.url or document.requested_url
            if not source_url:
                continue
            relation = self._automatic_relation(sources.get(self._url_key(source_url)))
            bucket = self._document_claim_candidates(
                content=document.content,
                source_url=source_url,
                relation=relation,
                terms=terms,
                subject_terms=subject_terms,
            )
            if bucket:
                buckets.append(bucket)

        output: list[ClaimCandidate] = []
        seen: set[tuple[str, str]] = set()
        position = 0
        while len(output) < limit and buckets:
            next_buckets: list[list[ClaimCandidate]] = []
            for bucket in buckets:
                if position < len(bucket):
                    candidate = bucket[position]
                    key = (
                        self._normalize(candidate.statement),
                        self._url_key(candidate.source_url),
                    )
                    if key not in seen:
                        seen.add(key)
                        output.append(candidate)
                        if len(output) >= limit:
                            break
                if position + 1 < len(bucket):
                    next_buckets.append(bucket)
            if len(output) >= limit:
                break
            position += 1
            buckets = next_buckets
        return output

    def _document_claim_candidates(
        self,
        *,
        content: str,
        source_url: str,
        relation: EvidenceRelation,
        terms: set[str],
        subject_terms: set[str],
    ) -> list[ClaimCandidate]:
        canonical = canonicalize_markdown(content)
        segments = re.split(r"(?<=[.!;])(?:\s+|\n+)|\n{2,}", canonical)
        ranked: list[tuple[int, int, ClaimCandidate]] = []
        for index, raw_segment in enumerate(segments, start=1):
            excerpt = re.sub(
                r"^(?:#{1,6}\s+|[-*+]\s+|>\s+)",
                "",
                raw_segment.strip(),
            ).strip()
            if not self._usable_statement(excerpt, terms, subject_terms):
                continue
            ranked.append(
                (
                    self._statement_score(excerpt, terms, subject_terms),
                    index,
                    ClaimCandidate(
                        statement=excerpt,
                        source_url=source_url,
                        locator=f"document_sentence:{index}",
                        excerpt=excerpt,
                        relation=relation,
                    ),
                )
            )
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [candidate for _, _, candidate in ranked]

    def _source_candidates_by_url(
        self,
        production: ProductionResearchResult,
    ) -> dict[str, SourceCandidate]:
        sources: dict[str, SourceCandidate] = {}
        for source in (*production.selected_sources, *production.source_candidates):
            sources.setdefault(self._url_key(source.url), source)
        return sources

    def _automatic_relation(self, source: SourceCandidate | None) -> EvidenceRelation:
        if source is None:
            return EvidenceRelation.CONTEXT_ONLY
        if source.source_type == "community_or_review":
            return EvidenceRelation.CONTEXT_ONLY
        if source.commercial_bias is CommercialBias.HIGH:
            return EvidenceRelation.CONTEXT_ONLY
        if source.intended_use is IntendedUse.CONTEXT_ONLY:
            return EvidenceRelation.CONTEXT_ONLY
        if (
            source.intended_use is IntendedUse.EVIDENCE_CANDIDATE
            or source.source_type in {"institutional", "editorial"}
        ):
            return EvidenceRelation.SUPPORTS
        return EvidenceRelation.CONTEXT_ONLY

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

    def _subject_terms(self, value: str) -> set[str]:
        base = self._topic_terms((value,)) - _SUBJECT_GENERIC_TERMS
        expanded = set(base)
        for term in base:
            expanded.update(_SUBJECT_SYNONYMS.get(term, set()))
            if len(term) >= 5:
                if term.endswith("s"):
                    expanded.add(term[:-1])
                else:
                    expanded.add(f"{term}s")
        return expanded

    def _usable_statement(
        self,
        statement: str,
        terms: set[str],
        subject_terms: set[str],
    ) -> bool:
        if len(statement) < 40 or len(statement) > 600:
            return False
        if statement.endswith("?"):
            return False
        normalized = self._normalize(statement)
        if normalized.startswith(("http://", "https://", "skip to ")):
            return False
        if "![" in statement:
            return False
        if _MARKDOWN_LINK_ONLY_RE.fullmatch(statement):
            return False
        if len(_MARKDOWN_LINK_RE.findall(statement)) >= 2:
            return False
        words = re.findall(r"[a-z0-9]+", normalized)
        if len(words) < 8:
            return False
        if len(words) <= 16 and not re.search(r"[.!;:]$", statement):
            return False
        statement_terms = set(words)
        if subject_terms and not statement_terms.intersection(subject_terms):
            return False
        if not terms:
            return True
        return bool(statement_terms.intersection(terms))

    def _statement_score(
        self,
        statement: str,
        terms: set[str],
        subject_terms: set[str],
    ) -> int:
        words = re.findall(r"[a-z0-9]+", self._normalize(statement))
        word_set = set(words)
        subject_overlap = len(word_set.intersection(subject_terms))
        overlap = len(word_set.intersection(terms))
        sentence_bonus = 3 if re.search(r"[.!;:]$", statement) else 0
        return subject_overlap * 50 + overlap * 10 + sentence_bonus + min(len(words), 40)

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    def _url_key(self, value: str) -> str:
        return value.strip().rstrip("/").casefold()

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
                "Originality gap remains: no usable approved MOTGU-owned material is "
                "attached to this opportunity. Reference-only items do not close this gap."
            )
        if any(document.content_truncated for document in production.documents):
            gaps.append("At least one evidence source was truncated during page reading.")
        return gaps
