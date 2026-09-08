"""Human admission of a KnowledgeCandidate after snapshot verification."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.candidates import (
    _RAW_PROVENANCE_KEYS,
    _RELATIONS,
    EXTRACTION_METHOD,
    _candidate_snapshot,
    _load_locked_evidence_set,
    rebuild_candidate_snapshot,
)
from app.modules.knowledge.models import Claim, KnowledgeCandidate

_DECISIONS = {"approve": "APPROVED", "reject": "REJECTED"}
_TERMINAL_STATUSES = {"APPROVED", "REJECTED"}
_PROVENANCE_KEYS = {
    "method",
    "evidence_set",
    "claim_id",
    "evidence_ids",
    "source_document_ids",
    "source_ids",
    "relation_counts",
    "evidence_refs",
    "candidate_content_hash",
}
_EVIDENCE_SET_KEYS = {"id", "version", "content_hash"}
_EVIDENCE_REF_KEYS = {
    "evidence_id",
    "relation",
    "locator",
    "source_document_ids",
    "source_ids",
    "provenance",
}


class KnowledgeCandidateAdmissionError(ValueError):
    """Raised when a candidate cannot safely transition through admission."""


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    return value


def _string(value: object, *, field: str, required: bool = True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    return value


def _uuid(value: object, *, field: str) -> UUID:
    raw = _string(value, field=field)
    try:
        return UUID(raw)
    except ValueError as exc:
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}") from exc


def _hash(value: object, *, field: str) -> str:
    raw = _string(value, field=field)
    if len(raw) != 64:
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    try:
        int(raw, 16)
    except ValueError as exc:
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}") from exc
    return raw


def _string_list(value: object, *, field: str, required: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    result = cast(list[str], value)
    if required and not result:
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    if any(not item.strip() for item in result):
        raise KnowledgeCandidateAdmissionError(f"candidate_invalid_{field}")
    if len(set(result)) != len(result):
        raise KnowledgeCandidateAdmissionError(f"candidate_duplicate_{field}")
    return result


def _contains_raw_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _RAW_PROVENANCE_KEYS
            or _contains_raw_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_raw_key(item) for item in value)
    return False


def _validate_snapshot_shape(candidate: KnowledgeCandidate) -> tuple[dict[str, Any], str]:
    provenance = _mapping(candidate.provenance_json, field="provenance")
    if set(provenance) != _PROVENANCE_KEYS:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_provenance")
    if provenance["method"] != EXTRACTION_METHOD:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_provenance_method")
    if not isinstance(candidate.statement, str) or not candidate.statement.strip():
        raise KnowledgeCandidateAdmissionError("candidate_invalid_statement")
    if not isinstance(candidate.summary, str) or not candidate.summary.strip():
        raise KnowledgeCandidateAdmissionError("candidate_invalid_summary")

    evidence_set = _mapping(provenance["evidence_set"], field="evidence_set")
    if set(evidence_set) != _EVIDENCE_SET_KEYS:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_set")
    _uuid(evidence_set["id"], field="evidence_set_id")
    version = evidence_set["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_set_version")
    _hash(evidence_set["content_hash"], field="evidence_set_content_hash")
    _uuid(provenance["claim_id"], field="claim_id")

    evidence_ids = _string_list(provenance["evidence_ids"], field="evidence_ids", required=True)
    for value in evidence_ids:
        _uuid(value, field="evidence_id")
    source_document_ids = _string_list(
        provenance["source_document_ids"], field="source_document_ids"
    )
    for value in source_document_ids:
        _uuid(value, field="source_document_id")
    source_ids = _string_list(provenance["source_ids"], field="source_ids", required=True)
    for value in source_ids:
        _uuid(value, field="source_id")

    entity_refs = candidate.entity_refs_json
    if not isinstance(entity_refs, list) or any(
        not isinstance(item, str) for item in entity_refs
    ):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_entity_refs")
    source_refs = candidate.source_refs_json
    if source_refs != [f"source:{source_id}" for source_id in source_ids]:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_source_refs")

    relation_counts = _mapping(provenance["relation_counts"], field="relation_counts")
    if set(relation_counts) != set(_RELATIONS):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_relation_counts")
    normalized_counts: dict[str, int] = {}
    for relation in _RELATIONS:
        count = relation_counts[relation]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise KnowledgeCandidateAdmissionError("candidate_invalid_relation_counts")
        normalized_counts[relation] = count
    if sum(normalized_counts.values()) != len(evidence_ids):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_relation_counts")

    evidence_refs_value = provenance["evidence_refs"]
    if not isinstance(evidence_refs_value, list) or len(evidence_refs_value) != len(evidence_ids):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_refs")
    evidence_refs: list[dict[str, Any]] = []
    ref_source_document_ids: set[str] = set()
    ref_source_ids: set[str] = set()
    ref_evidence_ids: list[str] = []
    for value in evidence_refs_value:
        evidence_ref = _mapping(value, field="evidence_ref")
        if set(evidence_ref) != _EVIDENCE_REF_KEYS:
            raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_ref")
        evidence_id = str(_uuid(evidence_ref["evidence_id"], field="evidence_ref_id"))
        relation = _string(evidence_ref["relation"], field="evidence_ref_relation")
        if relation not in _RELATIONS:
            raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_ref_relation")
        locator = _string(evidence_ref["locator"], field="evidence_ref_locator")
        ref_documents = _string_list(
            evidence_ref["source_document_ids"], field="evidence_ref_source_document_ids"
        )
        for source_document_id in ref_documents:
            _uuid(source_document_id, field="evidence_ref_source_document_id")
        ref_sources = _string_list(
            evidence_ref["source_ids"], field="evidence_ref_source_ids", required=True
        )
        for source_id in ref_sources:
            _uuid(source_id, field="evidence_ref_source_id")
        evidence_provenance = _mapping(
            evidence_ref["provenance"], field="evidence_ref_provenance"
        )
        if _contains_raw_key(evidence_provenance):
            raise KnowledgeCandidateAdmissionError("candidate_raw_provenance_rejected")
        ref_evidence_ids.append(evidence_id)
        ref_source_document_ids.update(ref_documents)
        ref_source_ids.update(ref_sources)
        evidence_refs.append(
            {
                "evidence_id": evidence_id,
                "relation": relation,
                "locator": locator,
                "source_document_ids": ref_documents,
                "source_ids": ref_sources,
                "provenance": dict(evidence_provenance),
            }
        )
    if ref_evidence_ids != evidence_ids:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_refs")
    if ref_source_document_ids != set(source_document_ids):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_source_document_refs")
    if ref_source_ids != set(source_ids):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_source_refs")
    if any(
        sum(item["relation"] == relation for item in evidence_refs)
        != normalized_counts[relation]
        for relation in _RELATIONS
    ):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_relation_counts")

    stored_hash = _hash(provenance["candidate_content_hash"], field="candidate_content_hash")
    snapshot, recomputed_hash = rebuild_candidate_snapshot(candidate)
    if snapshot["evidence_set"] != dict(evidence_set):
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_set")
    if snapshot["evidence_ids"] != evidence_ids:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_ids")
    if snapshot["source_document_ids"] != source_document_ids:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_source_document_ids")
    if snapshot["source_ids"] != source_ids:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_source_ids")
    if snapshot["relation_counts"] != normalized_counts:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_relation_counts")
    if snapshot["evidence_refs"] != evidence_refs:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_evidence_refs")
    if stored_hash != recomputed_hash:
        raise KnowledgeCandidateAdmissionError("candidate_content_hash_mismatch")
    return snapshot, recomputed_hash


async def _verify_current_lineage(
    session: AsyncSession,
    *,
    candidate: KnowledgeCandidate,
    candidate_snapshot: dict[str, Any],
    candidate_content_hash: str,
) -> None:
    evidence_set_data = _mapping(candidate_snapshot["evidence_set"], field="evidence_set")
    evidence_set_id = _uuid(evidence_set_data["id"], field="evidence_set_id")
    evidence_set, _content_case, locale, contexts = await _load_locked_evidence_set(
        session,
        evidence_set_id=evidence_set_id,
    )
    claim_id = _uuid(candidate_snapshot["claim_id"], field="claim_id")
    if evidence_set.project_id != candidate.project_id:
        raise KnowledgeCandidateAdmissionError("candidate_project_mismatch")
    if evidence_set.version != evidence_set_data["version"]:
        raise KnowledgeCandidateAdmissionError("candidate_evidence_set_version_mismatch")
    if evidence_set.content_hash != evidence_set_data["content_hash"]:
        raise KnowledgeCandidateAdmissionError("candidate_evidence_set_hash_mismatch")
    claim = await session.get(Claim, claim_id)
    if claim is None or claim.project_id != candidate.project_id:
        raise KnowledgeCandidateAdmissionError("candidate_claim_mismatch")
    claim_contexts = [context for context in contexts if context.evidence.claim_id == claim_id]
    if not claim_contexts:
        raise KnowledgeCandidateAdmissionError("candidate_claim_evidence_mismatch")
    current_snapshot, current_hash = _candidate_snapshot(
        evidence_set=evidence_set,
        claim=claim,
        locale=locale,
        contexts=claim_contexts,
    )
    if current_snapshot != candidate_snapshot or current_hash != candidate_content_hash:
        raise KnowledgeCandidateAdmissionError("candidate_snapshot_stale")


async def admit_knowledge_candidate(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    decision: str,
    reviewer: str,
    review_reason: str,
    expected_candidate_content_hash: str,
) -> KnowledgeCandidate:
    """Apply one verified human admission decision to a candidate."""

    target_status = _DECISIONS.get(decision)
    if target_status is None:
        raise KnowledgeCandidateAdmissionError("candidate_invalid_decision")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise KnowledgeCandidateAdmissionError("candidate_reviewer_required")
    if not isinstance(review_reason, str) or not review_reason.strip():
        raise KnowledgeCandidateAdmissionError("candidate_review_reason_required")
    if (
        not isinstance(expected_candidate_content_hash, str)
        or not expected_candidate_content_hash.strip()
    ):
        raise KnowledgeCandidateAdmissionError("candidate_expected_content_hash_required")

    candidate = await session.get(KnowledgeCandidate, candidate_id)
    if candidate is None:
        raise KnowledgeCandidateAdmissionError("candidate_not_found")
    if candidate.status not in {"CANDIDATE", *_TERMINAL_STATUSES}:
        raise KnowledgeCandidateAdmissionError("candidate_status_not_admissible")

    candidate_snapshot, recomputed_hash = _validate_snapshot_shape(candidate)
    stored_hash = _hash(
        candidate.provenance_json["candidate_content_hash"],
        field="candidate_content_hash",
    )
    expected_hash = _hash(
        expected_candidate_content_hash,
        field="expected_candidate_content_hash",
    )
    if not (expected_hash == recomputed_hash == stored_hash):
        raise KnowledgeCandidateAdmissionError("candidate_content_hash_mismatch")
    await _verify_current_lineage(
        session,
        candidate=candidate,
        candidate_snapshot=candidate_snapshot,
        candidate_content_hash=recomputed_hash,
    )

    normalized_reviewer = reviewer.strip()
    normalized_reason = review_reason.strip()
    if candidate.status in _TERMINAL_STATUSES:
        if (
            candidate.status == target_status
            and candidate.reviewer == normalized_reviewer
            and candidate.review_reason == normalized_reason
        ):
            return candidate
        raise KnowledgeCandidateAdmissionError("candidate_terminal_transition_rejected")

    candidate.status = target_status
    candidate.reviewer = normalized_reviewer
    candidate.review_reason = normalized_reason
    await session.flush()
    return candidate
