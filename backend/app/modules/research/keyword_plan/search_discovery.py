"""Bounded real Search Discovery into canonical Question Map planning signals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    HumanSelection,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.contracts import (
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchDepth,
    ResearchSignalKind,
    SearchSignal,
)
from app.modules.research.keyword_plan.classification_v2 import (
    classify_question_v2,
)
from app.modules.research.keyword_plan.content_architecture import (
    build_content_architecture,
)
from app.modules.research.keyword_plan.contracts import QueryQuality
from app.modules.research.keyword_plan.normalize import (
    normalize_text,
    signal_fingerprint,
)
from app.modules.research.keyword_plan.question_map import build_question_map

SEARCH_DISCOVERY_SCHEMA_VERSION = 1
SEARCH_DISCOVERY_POLICY_VERSION = "qm-search-discovery-v1"

_QUESTION_KINDS = {
    ResearchSignalKind.PEOPLE_ALSO_ASK,
    ResearchSignalKind.RELATED_SEARCH,
    ResearchSignalKind.AUTOCOMPLETE,
}
_CONTEXT_KINDS = {
    ResearchSignalKind.ORGANIC,
    ResearchSignalKind.SOURCE_DISCOVERY,
}
_KIND_PRIORITY = {
    ResearchSignalKind.PEOPLE_ALSO_ASK: 0,
    ResearchSignalKind.RELATED_SEARCH: 1,
    ResearchSignalKind.AUTOCOMPLETE: 2,
    ResearchSignalKind.ORGANIC: 3,
    ResearchSignalKind.SOURCE_DISCOVERY: 4,
}


class SearchDiscoveryError(ValueError):
    """Stable fail-closed bounded Search Discovery error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SearchDiscoveryRunner(Protocol):
    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult: ...


@dataclass(slots=True, frozen=True)
class SearchDiscoveryRequest:
    project_id: UUID
    need_id: UUID
    locale: str
    country: str
    seed_queries: tuple[str, ...]
    artifact_ref: str | None = None
    result_limit: int = 10
    max_hops: int = 1
    max_expansions_per_hop: int = 4
    max_total_queries: int = 8


@dataclass(slots=True, frozen=True)
class SearchDiscoveryObservation:
    provider: str
    method: str
    query: str
    hop: int
    text: str
    normalized_text: str
    question_eligible: bool
    source_url: str | None
    title: str | None
    snippet: str | None
    position: int | None

    @property
    def observation_key(self) -> str:
        payload = {
            "provider": self.provider,
            "method": self.method,
            "query": normalize_text(self.query),
            "text": self.normalized_text,
            "source_url": (self.source_url or "").strip(),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True)
class SearchDiscoveryResult:
    schema_version: int
    policy_version: str
    project_id: UUID
    need_id: UUID
    locale: str
    country: str
    seed_queries: list[str]
    executed_queries: list[dict[str, object]] = field(default_factory=list)
    observations: list[SearchDiscoveryObservation] = field(default_factory=list)
    persisted_signal_ids: list[UUID] = field(default_factory=list)
    created_signal_ids: list[UUID] = field(default_factory=list)
    reused_signal_ids: list[UUID] = field(default_factory=list)
    provider_decisions: list[dict[str, object]] = field(default_factory=list)
    provider_calls: list[dict[str, object]] = field(default_factory=list)
    question_map_snapshot_hash: str = ""
    architecture_snapshot_hash: str = ""
    question_count: int = 0
    cluster_count: int = 0
    pillar_candidate_count: int = 0
    breadth: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "project_id": str(self.project_id),
            "need_id": str(self.need_id),
            "locale": self.locale,
            "country": self.country,
            "seed_queries": list(self.seed_queries),
            "executed_queries": self.executed_queries,
            "observations": [asdict(row) for row in self.observations],
            "persisted_signal_ids": [
                str(value) for value in self.persisted_signal_ids
            ],
            "created_signal_ids": [
                str(value) for value in self.created_signal_ids
            ],
            "reused_signal_ids": [
                str(value) for value in self.reused_signal_ids
            ],
            "provider_decisions": self.provider_decisions,
            "provider_calls": self.provider_calls,
            "question_map_snapshot_hash": self.question_map_snapshot_hash,
            "architecture_snapshot_hash": self.architecture_snapshot_hash,
            "question_count": self.question_count,
            "cluster_count": self.cluster_count,
            "pillar_candidate_count": self.pillar_candidate_count,
            "breadth": self.breadth,
            "semantics": {
                "planning_language_only": True,
                "not_customer_truth": True,
                "not_factual_evidence": True,
                "does_not_mutate_need_status": True,
                "does_not_select_content": True,
                "does_not_materialize_content": True,
            },
        }


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _clean_locale(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized:
        raise SearchDiscoveryError("search_discovery_locale_required")
    return normalized


def _clean_country(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized:
        raise SearchDiscoveryError("search_discovery_country_required")
    return normalized


def _clean_queries(values: tuple[str, ...]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        query = value.strip()
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(query)
    if not output:
        raise SearchDiscoveryError("search_discovery_seed_queries_required")
    return output


def _validate_bounds(request: SearchDiscoveryRequest) -> None:
    if request.result_limit < 1 or request.result_limit > 50:
        raise SearchDiscoveryError("search_discovery_result_limit_invalid")
    if request.max_hops < 0 or request.max_hops > 2:
        raise SearchDiscoveryError("search_discovery_max_hops_invalid")
    if (
        request.max_expansions_per_hop < 1
        or request.max_expansions_per_hop > 10
    ):
        raise SearchDiscoveryError(
            "search_discovery_expansion_limit_invalid"
        )
    if request.max_total_queries < 1 or request.max_total_queries > 20:
        raise SearchDiscoveryError(
            "search_discovery_total_query_limit_invalid"
        )


def _signal_text(raw: SearchSignal) -> str:
    for value in (raw.text, raw.title or "", raw.snippet or ""):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return ""


def _observation(
    raw: SearchSignal,
    *,
    hop: int,
) -> SearchDiscoveryObservation | None:
    if raw.kind not in _QUESTION_KINDS | _CONTEXT_KINDS:
        return None
    text = _signal_text(raw)
    normalized = normalize_text(text)
    if not normalized:
        return None
    return SearchDiscoveryObservation(
        provider=raw.provider.strip().casefold(),
        method=raw.kind.value,
        query=raw.query.strip(),
        hop=hop,
        text=text,
        normalized_text=normalized,
        question_eligible=raw.kind in _QUESTION_KINDS,
        source_url=raw.url,
        title=raw.title,
        snippet=raw.snippet,
        position=raw.position,
    )


def _expansion_candidate(
    observation: SearchDiscoveryObservation,
    *,
    locale: str,
) -> bool:
    if not observation.question_eligible:
        return False
    classification = classify_question_v2(
        observation.text,
        locale=locale,
    )
    if classification.classification_status != "classified":
        return False
    return classification.query_quality is QueryQuality.USABLE


def _observation_sort_key(
    row: SearchDiscoveryObservation,
) -> tuple[object, ...]:
    try:
        kind = ResearchSignalKind(row.method)
    except ValueError:
        priority = 99
    else:
        priority = _KIND_PRIORITY.get(kind, 99)
    return (
        priority,
        row.normalized_text,
        row.provider,
        normalize_text(row.query),
        row.source_url or "",
        row.observation_key,
    )


def _canonical_signal_id(
    *,
    project_id: UUID,
    locale: str,
    fingerprint: str,
) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        (
            "https://contentengine.motgu/qm-search-discovery/v1/"
            f"{project_id}/{locale}/{fingerprint}"
        ),
    )


def _observation_payload(
    row: SearchDiscoveryObservation,
    *,
    captured_at: str,
) -> dict[str, object]:
    return {
        "observation_key": row.observation_key,
        "provider": row.provider,
        "method": row.method,
        "query": row.query,
        "hop": row.hop,
        "text": row.text,
        "source_url": row.source_url,
        "title": row.title,
        "snippet": row.snippet,
        "position": row.position,
        "question_eligible": row.question_eligible,
        "captured_at": captured_at,
    }


def _payload_observation_key(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    key = value.get("observation_key")
    if not isinstance(key, str) or not key:
        return None
    return key


def _representative_occurrence(
    occurrences: list[dict[str, object]],
) -> dict[str, object]:
    if not occurrences:
        raise SearchDiscoveryError(
            "search_discovery_provenance_observations_required"
        )

    def key(row: dict[str, object]) -> tuple[object, ...]:
        method = str(row.get("method", ""))
        try:
            kind = ResearchSignalKind(method)
        except ValueError:
            priority = 99
        else:
            priority = _KIND_PRIORITY.get(kind, 99)
        return (
            priority,
            normalize_text(str(row.get("text", ""))),
            str(row.get("provider", "")),
            normalize_text(str(row.get("query", ""))),
            str(row.get("source_url", "")),
            str(row.get("observation_key", "")),
        )

    return sorted(occurrences, key=key)[0]


def _merged_occurrences(
    existing: object,
    additions: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = existing if isinstance(existing, list) else []
    merged: dict[str, dict[str, object]] = {}
    for raw in [*rows, *additions]:
        key = _payload_observation_key(raw)
        if key is None or not isinstance(raw, dict):
            continue
        merged[key] = {str(name): value for name, value in raw.items()}
    return [merged[key] for key in sorted(merged)]


async def _persist_observation_groups(
    session: AsyncSession,
    *,
    request: SearchDiscoveryRequest,
    observations: list[SearchDiscoveryObservation],
    captured_at: str,
) -> tuple[list[UUID], list[UUID], list[UUID]]:
    grouped: dict[str, list[SearchDiscoveryObservation]] = {}
    for row in observations:
        grouped.setdefault(row.normalized_text, []).append(row)

    persisted: list[UUID] = []
    created: list[UUID] = []
    reused: list[UUID] = []
    locale = _clean_locale(request.locale)

    for normalized in sorted(grouped):
        group = sorted(grouped[normalized], key=_observation_sort_key)
        fingerprint = signal_fingerprint(
            locale=locale,
            observed_text=group[0].text,
        )
        signal_id = _canonical_signal_id(
            project_id=request.project_id,
            locale=locale,
            fingerprint=fingerprint,
        )
        additions = [
            _observation_payload(row, captured_at=captured_at)
            for row in group
        ]

        signal = await session.get(Signal, signal_id)
        if signal is None:
            occurrences = _merged_occurrences([], additions)
            representative = _representative_occurrence(occurrences)
            signal = Signal(
                id=signal_id,
                project_id=request.project_id,
                source_kind="SEARCH",
                scope="market_web",
                observed_text=str(representative["text"]),
                source_url=(
                    str(representative["source_url"])
                    if representative.get("source_url")
                    else None
                ),
                external_id=None,
                locale=locale,
                context=(
                    "qm_search_discovery:"
                    f"{representative['method']}:"
                    f"{representative['query']}"
                ),
                captured_at=datetime.fromisoformat(captured_at),
                observed_at=None,
                fingerprint=fingerprint,
                duplicate_of_id=None,
                independence_group=fingerprint,
                provenance_json={},
            )
            session.add(signal)
            created.append(signal.id)
        else:
            if (
                signal.project_id != request.project_id
                or signal.source_kind != "SEARCH"
                or signal.scope != "market_web"
                or signal.locale.strip().casefold() != locale
                or signal.fingerprint != fingerprint
            ):
                raise SearchDiscoveryError(
                    "search_discovery_signal_identity_conflict"
                )
            reused.append(signal.id)

        prior = signal.provenance_json or {}
        occurrences = _merged_occurrences(
            prior.get("observations"),
            additions,
        )
        representative = _representative_occurrence(occurrences)
        question_eligible = any(
            bool(row.get("question_eligible"))
            for row in occurrences
        )

        signal.observed_text = str(representative["text"])
        signal.source_url = (
            str(representative["source_url"])
            if representative.get("source_url")
            else None
        )
        signal.context = (
            "qm_search_discovery:"
            f"{representative['method']}:"
            f"{representative['query']}"
        )
        signal.independence_group = fingerprint
        signal.provenance_json = {
            "origin": SEARCH_DISCOVERY_POLICY_VERSION,
            "provider": representative.get("provider"),
            "method": representative.get("method"),
            "locator": representative.get("query"),
            "source_ref": representative.get("source_url"),
            "artifact_ref": request.artifact_ref,
            "question_eligible": question_eligible,
            "customer_truth_eligible": False,
            "factual_evidence_eligible": False,
            "independence_policy": "normalized_query_fingerprint",
            "observation_count": len(occurrences),
            "observations": occurrences,
        }

        link = await session.get(
            NeedHypothesisSignal,
            (request.need_id, signal.id, "supports"),
        )
        if link is None:
            session.add(
                NeedHypothesisSignal(
                    need_hypothesis_id=request.need_id,
                    signal_id=signal.id,
                    relation="supports",
                )
            )
        persisted.append(signal.id)

    await session.flush()
    return (
        sorted(set(persisted), key=str),
        sorted(set(created), key=str),
        sorted(set(reused), key=str),
    )


def _provider_decisions(
    result: ProductionResearchResult,
    *,
    query: str,
    hop: int,
) -> list[dict[str, object]]:
    return [
        {
            "query": query,
            "hop": hop,
            "provider": row.provider,
            "status": row.status.value,
            "reason": row.reason,
            "failure_class": row.failure_class,
        }
        for row in result.decisions
    ]


def _provider_calls(
    result: ProductionResearchResult,
    *,
    query: str,
    hop: int,
) -> list[dict[str, object]]:
    return [
        {
            "query": query,
            "hop": hop,
            "provider": row.provider,
            "operation": row.operation,
            "purpose": row.purpose,
            "status": row.status,
            "result_count": row.result_count,
            "reason": row.reason,
            "captured_at": row.captured_at,
        }
        for row in result.calls
    ]


def _breadth(
    architecture: dict[str, object],
) -> list[dict[str, object]]:
    candidates = architecture.get("candidates")
    if not isinstance(candidates, list):
        raise SearchDiscoveryError(
            "search_discovery_architecture_candidates_invalid"
        )
    output: list[dict[str, object]] = []
    for raw in candidates:
        if not isinstance(raw, dict) or raw.get("role") != "cluster":
            continue
        output.append(
            {
                "candidate_key": raw.get("candidate_key"),
                "intent": raw.get("intent"),
                "audience_stage": raw.get("audience_stage"),
                "answer_job": raw.get("answer_job"),
                "primary_question": raw.get("primary_question"),
                "question_count": raw.get("question_count"),
                "coverage_status": raw.get("coverage_status"),
                "decision": raw.get("decision"),
                "selection_readiness": raw.get("selection_readiness"),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            str(row.get("audience_stage", "")),
            str(row.get("answer_job", "")),
            str(row.get("candidate_key", "")),
        ),
    )


async def run_search_discovery(
    session: AsyncSession,
    *,
    runner: SearchDiscoveryRunner,
    request: SearchDiscoveryRequest,
) -> SearchDiscoveryResult:
    """Run bounded external search and persist planning-only canonical SEARCH Signals."""

    _validate_bounds(request)
    locale = _clean_locale(request.locale)
    country = _clean_country(request.country)
    seeds = _clean_queries(request.seed_queries)
    if len(seeds) > request.max_total_queries:
        raise SearchDiscoveryError(
            "search_discovery_seed_count_exceeds_total_query_limit"
        )

    project = await session.get(Project, request.project_id)
    if project is None:
        raise SearchDiscoveryError("search_discovery_project_not_found")
    need = await session.get(NeedHypothesis, request.need_id)
    if need is None or need.project_id != project.id:
        raise SearchDiscoveryError("search_discovery_need_not_found")

    before_need_state = (
        need.status,
        need.version,
        need.reviewed_by,
        need.reviewed_at,
        need.review_reason,
    )
    before_counts = {
        "opportunities": int(
            await session.scalar(
                select(func.count())
                .select_from(ContentOpportunity)
                .where(ContentOpportunity.project_id == project.id)
            )
            or 0
        ),
        "selections": int(
            await session.scalar(
                select(func.count())
                .select_from(HumanSelection)
                .join(
                    ContentOpportunity,
                    ContentOpportunity.id
                    == HumanSelection.content_opportunity_id,
                )
                .where(ContentOpportunity.project_id == project.id)
            )
            or 0
        ),
        "cases": int(
            await session.scalar(
                select(func.count())
                .select_from(ContentCase)
                .where(ContentCase.project_id == project.id)
            )
            or 0
        ),
    }

    captured_at = datetime.now(UTC).isoformat()
    result = SearchDiscoveryResult(
        schema_version=SEARCH_DISCOVERY_SCHEMA_VERSION,
        policy_version=SEARCH_DISCOVERY_POLICY_VERSION,
        project_id=project.id,
        need_id=need.id,
        locale=locale,
        country=country,
        seed_queries=seeds,
    )

    seen_queries = {normalize_text(value) for value in seeds}
    frontier = list(seeds)
    observations: list[SearchDiscoveryObservation] = []
    total_queries = 0

    for hop in range(request.max_hops + 1):
        if not frontier or total_queries >= request.max_total_queries:
            break
        current = frontier[: request.max_total_queries - total_queries]
        next_candidates: dict[str, SearchDiscoveryObservation] = {}

        for query in current:
            research = await runner.run(
                session,
                request=ProductionResearchRequest(
                    project_id=project.id,
                    query=query,
                    locale=locale,
                    country=country,
                    limit=request.result_limit,
                    depth=ResearchDepth.STANDARD,
                    max_pages_to_read=0,
                    force_external_discovery=True,
                ),
            )
            total_queries += 1
            result.executed_queries.append(
                {
                    "query": query,
                    "hop": hop,
                    "stop_reason": research.stop_reason,
                    "sufficient": research.sufficient,
                    "signal_count": len(research.signals),
                    "source_count": len(research.source_candidates),
                }
            )
            result.provider_decisions.extend(
                _provider_decisions(
                    research,
                    query=query,
                    hop=hop,
                )
            )
            result.provider_calls.extend(
                _provider_calls(
                    research,
                    query=query,
                    hop=hop,
                )
            )

            for raw in research.signals:
                row = _observation(raw, hop=hop)
                if row is None:
                    continue
                observations.append(row)
                if hop >= request.max_hops:
                    continue
                if not _expansion_candidate(row, locale=locale):
                    continue
                normalized = row.normalized_text
                if normalized in seen_queries:
                    continue
                prior = next_candidates.get(normalized)
                if (
                    prior is None
                    or _observation_sort_key(row)
                    < _observation_sort_key(prior)
                ):
                    next_candidates[normalized] = row

        if hop >= request.max_hops:
            break
        ordered = sorted(
            next_candidates.values(),
            key=_observation_sort_key,
        )
        frontier = [
            row.text
            for row in ordered[: request.max_expansions_per_hop]
        ]
        seen_queries.update(normalize_text(value) for value in frontier)

    observations.sort(key=_observation_sort_key)
    result.observations = observations

    persisted, created, reused = await _persist_observation_groups(
        session,
        request=request,
        observations=observations,
        captured_at=captured_at,
    )
    result.persisted_signal_ids = persisted
    result.created_signal_ids = created
    result.reused_signal_ids = reused

    question_map_first = await build_question_map(
        session,
        project_id=project.id,
        need_id=need.id,
        locale=locale,
    )
    question_map_second = await build_question_map(
        session,
        project_id=project.id,
        need_id=need.id,
        locale=locale,
    )
    if question_map_first != question_map_second:
        raise SearchDiscoveryError(
            "search_discovery_question_map_nondeterministic"
        )

    architecture_first = await build_content_architecture(
        session,
        project_id=project.id,
        need_id=need.id,
        locale=locale,
    )
    architecture_second = await build_content_architecture(
        session,
        project_id=project.id,
        need_id=need.id,
        locale=locale,
    )
    if architecture_first != architecture_second:
        raise SearchDiscoveryError(
            "search_discovery_architecture_nondeterministic"
        )

    question_counts = question_map_first.get("counts")
    cluster_summary = question_map_first.get("cluster_summary")
    architecture_counts = architecture_first.get("counts")
    if (
        not isinstance(question_counts, dict)
        or not isinstance(cluster_summary, dict)
        or not isinstance(architecture_counts, dict)
    ):
        raise SearchDiscoveryError(
            "search_discovery_projection_counts_invalid"
        )

    result.question_map_snapshot_hash = str(
        question_map_first["snapshot_hash"]
    )
    result.architecture_snapshot_hash = str(
        architecture_first["snapshot_hash"]
    )
    result.question_count = int(question_counts.get("questions", 0))
    result.cluster_count = int(cluster_summary.get("clusters", 0))
    result.pillar_candidate_count = int(
        architecture_counts.get("pillar_candidates", 0)
    )
    result.breadth = _breadth(architecture_first)

    await session.refresh(need)
    after_need_state = (
        need.status,
        need.version,
        need.reviewed_by,
        need.reviewed_at,
        need.review_reason,
    )
    if after_need_state != before_need_state:
        raise SearchDiscoveryError(
            "search_discovery_need_state_mutated"
        )

    after_counts = {
        "opportunities": int(
            await session.scalar(
                select(ContentOpportunity)
                .where(ContentOpportunity.project_id == project.id)
                .with_only_columns(
                    __import__("sqlalchemy").func.count()
                )
            )
            or 0
        ),
        "selections": int(
            await session.scalar(
                select(HumanSelection)
                .join(
                    ContentOpportunity,
                    ContentOpportunity.id
                    == HumanSelection.content_opportunity_id,
                )
                .where(ContentOpportunity.project_id == project.id)
                .with_only_columns(
                    __import__("sqlalchemy").func.count()
                )
            )
            or 0
        ),
        "cases": int(
            await session.scalar(
                select(ContentCase)
                .where(ContentCase.project_id == project.id)
                .with_only_columns(
                    __import__("sqlalchemy").func.count()
                )
            )
            or 0
        ),
    }
    if after_counts != before_counts:
        raise SearchDiscoveryError(
            "search_discovery_unexpected_content_mutation"
        )

    return result


def capture_hash(result: SearchDiscoveryResult) -> str:
    """Hash stable discovery semantics while excluding run timestamps."""

    payload = result.as_dict()
    payload.pop("created_signal_ids", None)
    payload.pop("reused_signal_ids", None)
    calls = payload.get("provider_calls")
    if isinstance(calls, list):
        payload["provider_calls"] = [
            {
                key: value
                for key, value in row.items()
                if key != "captured_at"
            }
            if isinstance(row, dict)
            else row
            for row in calls
        ]
    observations = payload.get("observations")
    if isinstance(observations, list):
        payload["observations"] = sorted(
            observations,
            key=lambda row: json.dumps(
                row,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ),
        )
    return _stable_hash(payload)


__all__ = [
    "SEARCH_DISCOVERY_POLICY_VERSION",
    "SEARCH_DISCOVERY_SCHEMA_VERSION",
    "SearchDiscoveryError",
    "SearchDiscoveryRequest",
    "SearchDiscoveryResult",
    "SearchDiscoveryRunner",
    "capture_hash",
    "run_search_discovery",
]
