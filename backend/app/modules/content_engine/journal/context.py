"""CE05 Journal context assembly and bounded internal-memory recall."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.memory_gap import MemoryGapReport, recommend_memory_gap
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.knowledge.models import KnowledgeCandidate

MAX_APPROVED_KNOWLEDGE = 8
_UPSTREAM_DECISION_LOCKS = {"MERGE", "LINK_ONLY", "DO_NOT_WRITE"}
_RAW_PROVENANCE_KEYS = {
    "body",
    "html",
    "payload",
    "raw",
    "raw_payload",
    "raw_response",
    "response",
    "result",
}


class JournalContextError(ValueError):
    """Raised when a Journal context is not safe to assemble."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class ApprovedKnowledge:
    id: UUID
    locale: str | None
    statement: str
    summary: str
    source_refs: tuple[str, ...]
    provenance: dict[str, object]
    relevance: int

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "locale": self.locale,
            "statement": self.statement,
            "summary": self.summary,
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
            "relevance": self.relevance,
        }


@dataclass(frozen=True, slots=True)
class MemoryOverlap:
    report: MemoryGapReport
    effective_decision: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            **self.report.to_dict(),
            "effective_decision": self.effective_decision,
            "upstream_decision_is_authoritative": (
                self.report.stored_opportunity_decision in _UPSTREAM_DECISION_LOCKS
            ),
        }


@dataclass(frozen=True, slots=True)
class JournalContext:
    content_case_id: UUID
    locale_variant_id: UUID
    opportunity_id: UUID
    need_hypothesis_id: UUID
    locale: str
    content_case: dict[str, object]
    locale_variant: dict[str, object]
    opportunity: dict[str, object]
    need_hypothesis: dict[str, object]
    approved_knowledge: tuple[ApprovedKnowledge, ...]
    memory_overlap: MemoryOverlap
    provider_calls: int = 0
    schema_version: int = 1

    @property
    def approved_knowledge_refs(self) -> tuple[str, ...]:
        return tuple(f"knowledge_candidate:{item.id}" for item in self.approved_knowledge)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "content_case_id": str(self.content_case_id),
            "locale_variant_id": str(self.locale_variant_id),
            "opportunity_id": str(self.opportunity_id),
            "need_hypothesis_id": str(self.need_hypothesis_id),
            "locale": self.locale,
            "content_case": self.content_case,
            "locale_variant": self.locale_variant,
            "opportunity": self.opportunity,
            "need_hypothesis": self.need_hypothesis,
            "approved_knowledge": [item.to_dict() for item in self.approved_knowledge],
            "approved_knowledge_refs": list(self.approved_knowledge_refs),
            "memory_overlap": self.memory_overlap.to_dict(),
            "provider_calls": self.provider_calls,
        }

    @property
    def content_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PersistedJournalContext:
    journal_context_artifact: Artifact
    memory_overlap_artifact: Artifact
    context_manifest_id: UUID


def _tokens(*values: str) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for token in re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE):
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            result.append(token)
    return tuple(result)


def _contains_raw_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _RAW_PROVENANCE_KEYS or _contains_raw_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_raw_key(item) for item in value)
    return False


def _candidate_knowledge(
    candidate: KnowledgeCandidate,
    *,
    query_terms: tuple[str, ...],
) -> ApprovedKnowledge | None:
    source_refs = candidate.source_refs_json
    provenance = candidate.provenance_json
    if not source_refs or any(not isinstance(ref, str) or not ref.strip() for ref in source_refs):
        raise JournalContextError("approved_knowledge_missing_provenance", str(candidate.id))
    if not isinstance(provenance, dict) or not provenance or _contains_raw_key(provenance):
        raise JournalContextError("approved_knowledge_invalid_provenance", str(candidate.id))

    searchable = f"{candidate.statement} {candidate.summary}".casefold()
    relevance = sum(term in searchable for term in query_terms)
    if relevance == 0:
        return None
    return ApprovedKnowledge(
        id=candidate.id,
        locale=candidate.locale,
        statement=candidate.statement,
        summary=candidate.summary,
        source_refs=tuple(source_refs),
        provenance=dict(provenance),
        relevance=relevance,
    )


async def _recall_approved_knowledge(
    session: AsyncSession,
    *,
    project_id: UUID,
    locale: str,
    query_terms: tuple[str, ...],
    limit: int,
) -> tuple[ApprovedKnowledge, ...]:
    candidates = (
        await session.scalars(
            select(KnowledgeCandidate)
            .where(
                KnowledgeCandidate.project_id == project_id,
                KnowledgeCandidate.status == "APPROVED",
                (KnowledgeCandidate.locale.is_(None) | (KnowledgeCandidate.locale == locale)),
            )
            .order_by(KnowledgeCandidate.id)
        )
    ).all()

    matched = [
        knowledge
        for candidate in candidates
        if (knowledge := _candidate_knowledge(candidate, query_terms=query_terms)) is not None
    ]
    matched.sort(key=lambda item: (-item.relevance, str(item.id)))
    return tuple(matched[:limit])


def _case_payload(content_case: ContentCase) -> dict[str, object]:
    return {
        "id": str(content_case.id),
        "project_id": str(content_case.project_id),
        "content_type": content_case.content_type,
        "audience_hypothesis_id": (
            str(content_case.audience_hypothesis_id)
            if content_case.audience_hypothesis_id is not None
            else None
        ),
        "need_hypothesis_id": str(content_case.need_hypothesis_id),
        "content_opportunity_id": str(content_case.content_opportunity_id),
        "desired_action": content_case.desired_action,
        "content_hypothesis": content_case.content_hypothesis,
        "originality_statement": content_case.originality_statement,
        "reader_before": content_case.reader_before,
        "reader_after": content_case.reader_after,
        "status": content_case.status,
    }


def _variant_payload(variant: LocaleVariant) -> dict[str, object]:
    return {
        "id": str(variant.id),
        "content_case_id": str(variant.content_case_id),
        "locale": variant.locale,
        "content_role": variant.content_role,
        "primary_question": variant.primary_question,
        "primary_intent": variant.primary_intent,
        "secondary_intent": variant.secondary_intent,
        "primary_query": variant.primary_query,
        "keyword_notes": variant.keyword_notes_json,
        "emotion_arc": variant.emotion_arc_json,
        "must_include": variant.must_include_json,
        "must_not_claim": variant.must_not_claim_json,
        "status": variant.status,
    }


def _opportunity_payload(opportunity: ContentOpportunity) -> dict[str, object]:
    return {
        "id": str(opportunity.id),
        "project_id": str(opportunity.project_id),
        "need_hypothesis_id": str(opportunity.need_hypothesis_id),
        "locale": opportunity.locale,
        "reader": opportunity.reader,
        "situation": opportunity.situation,
        "need": opportunity.need,
        "question": opportunity.question,
        "intent": opportunity.intent,
        "promise": opportunity.promise,
        "motgu_material_refs": opportunity.motgu_material_refs_json,
        "material_gaps": opportunity.material_gaps_json,
        "existing_content_refs": opportunity.existing_content_refs_json,
        "what_is_actually_new": opportunity.what_is_actually_new,
        "decision": opportunity.decision,
        "priority": opportunity.priority,
        "version": opportunity.version,
        "selected_by": opportunity.selected_by,
        "selected_at": (
            opportunity.selected_at.isoformat() if opportunity.selected_at is not None else None
        ),
        "selection_reason": opportunity.selection_reason,
    }


def _need_payload(need: NeedHypothesis) -> dict[str, object]:
    return {
        "id": str(need.id),
        "project_id": str(need.project_id),
        "audience_hypothesis_id": (
            str(need.audience_hypothesis_id) if need.audience_hypothesis_id is not None else None
        ),
        "type": need.type,
        "statement": need.statement,
        "audience_scope": need.audience_scope,
        "situation": need.situation,
        "origin": need.origin,
        "status": need.status,
        "alternative_explanations": need.alternative_explanations_json,
        "missing_evidence": need.missing_evidence_json,
        "version": need.version,
    }


async def build_journal_context(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
    refresh_before: datetime | None = None,
    knowledge_limit: int = MAX_APPROVED_KNOWLEDGE,
) -> JournalContext:
    """Build a bounded, provider-free Journal context from persisted records."""

    if not 1 <= knowledge_limit <= MAX_APPROVED_KNOWLEDGE:
        raise JournalContextError("journal_context_knowledge_limit_invalid")

    row = (
        await session.execute(
            select(ContentCase, LocaleVariant, ContentOpportunity, NeedHypothesis)
            .join(LocaleVariant, LocaleVariant.content_case_id == ContentCase.id)
            .join(ContentOpportunity, ContentOpportunity.id == ContentCase.content_opportunity_id)
            .join(NeedHypothesis, NeedHypothesis.id == ContentCase.need_hypothesis_id)
            .where(
                ContentCase.id == content_case_id,
                LocaleVariant.id == locale_variant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise JournalContextError("journal_context_case_or_variant_not_found")
    content_case, variant, opportunity, need = row

    if content_case.content_type != "journal":
        raise JournalContextError("journal_context_requires_journal_case")
    if (
        content_case.project_id != opportunity.project_id
        or content_case.project_id != need.project_id
    ):
        raise JournalContextError("journal_context_project_mismatch")
    if content_case.need_hypothesis_id != opportunity.need_hypothesis_id:
        raise JournalContextError("journal_context_hypothesis_mismatch")
    if variant.locale != opportunity.locale:
        raise JournalContextError("journal_context_locale_mismatch")
    if opportunity.suggested_content_type != "journal":
        raise JournalContextError("journal_context_opportunity_type_mismatch")
    if opportunity.selected_by is None:
        raise JournalContextError("journal_context_opportunity_not_selected")

    memory_report = await recommend_memory_gap(
        session,
        content_opportunity_id=opportunity.id,
        refresh_before=refresh_before,
    )
    effective_decision = (
        opportunity.decision
        if opportunity.decision in _UPSTREAM_DECISION_LOCKS
        else memory_report.recommendation
    )
    query_terms = _tokens(
        opportunity.question,
        opportunity.need,
        opportunity.reader,
        need.statement,
        variant.primary_question,
    )
    approved_knowledge = await _recall_approved_knowledge(
        session,
        project_id=content_case.project_id,
        locale=variant.locale,
        query_terms=query_terms,
        limit=knowledge_limit,
    )
    return JournalContext(
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        opportunity_id=opportunity.id,
        need_hypothesis_id=need.id,
        locale=variant.locale,
        content_case=_case_payload(content_case),
        locale_variant=_variant_payload(variant),
        opportunity=_opportunity_payload(opportunity),
        need_hypothesis=_need_payload(need),
        approved_knowledge=approved_knowledge,
        memory_overlap=MemoryOverlap(memory_report, effective_decision),
    )


async def _persist_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    artifact_type: str,
    locale: str,
    payload: dict[str, object],
) -> Artifact:
    content_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    existing = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact_type,
            Artifact.content_hash == content_hash,
        )
        .order_by(Artifact.version, Artifact.id)
        .limit(1)
    )
    if existing is not None:
        return existing
    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact_type,
        )
    )
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        locale=locale,
        version=int(current_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def persist_journal_context(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    context: JournalContext,
) -> PersistedJournalContext:
    """Persist the PR-A artifacts and bind the exact context to a CE03 manifest."""

    run = await session.get(ContentRun, run_id)
    step = await session.get(StepRun, step_run_id)
    if run is None or run.content_case_id != context.content_case_id:
        raise JournalContextError("journal_context_run_mismatch")
    if step is None or step.run_id != run.id:
        raise JournalContextError("journal_context_step_mismatch")
    if run.locale_variant_id != context.locale_variant_id:
        raise JournalContextError("journal_context_run_locale_mismatch")

    memory_artifact = await _persist_artifact(
        session,
        run_id=run.id,
        step_run_id=step.id,
        artifact_type="memory_overlap",
        locale=context.locale,
        payload=context.memory_overlap.to_dict(),
    )
    context_artifact = await _persist_artifact(
        session,
        run_id=run.id,
        step_run_id=step.id,
        artifact_type="journal_context",
        locale=context.locale,
        payload=context.to_dict(),
    )
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version="journal_context:1",
            recipe_version="journal_context:1",
            context_artifact_id=context_artifact.id,
            approved_knowledge_refs=context.approved_knowledge_refs,
        ),
    )
    return PersistedJournalContext(
        journal_context_artifact=context_artifact,
        memory_overlap_artifact=memory_artifact,
        context_manifest_id=manifest.id,
    )


__all__ = [
    "ApprovedKnowledge",
    "JournalContext",
    "JournalContextError",
    "MAX_APPROVED_KNOWLEDGE",
    "MemoryOverlap",
    "PersistedJournalContext",
    "build_journal_context",
    "persist_journal_context",
]
