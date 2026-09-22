"""PM-01 safe publication package, authorization and WordPress handoff."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.operator_quality import get_quality_progress
from app.modules.content_engine.models import (
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentItemJourneyStage,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ContextManifest,
    Job,
    StepRun,
    utc_now,
)
from app.modules.harness.outbox import (
    OutboxIntent,
    ReconciliationResult,
    SideEffectExecutionResult,
    apply_reconciliation_result,
    complete_outbox_intent,
    create_outbox_intent,
    mark_outbox_needs_reconciliation,
    prepare_outbox_dispatch,
)
from app.modules.harness.persistence import (
    complete_job,
    enqueue_job,
    fail_job_and_maybe_retry,
    get_latest_checkpoint,
    pause_for_approval,
    resolve_approval,
    transition_run,
)
from app.modules.harness.policy import RetryPolicy
from app.modules.publishing.models import PublishedContent, PublishEvent

PUBLISH_PACKAGE_ARTIFACT_TYPE = "publish_package"
PUBLISH_AUTHORIZATION_STEP = "publish_authorization"
WORDPRESS_STEP = "wordpress_publish"
PUBLISH_PACKAGE_SCHEMA_VERSION = 1
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PublishDecision = Literal["approved", "rejected"]
PublishAction = Literal["draft", "publish"]
WordPressReconcileOutcome = Literal[
    "confirmed_success",
    "confirmed_absent",
    "conflict",
    "unknown",
]


class PublishError(ValueError):
    """Stable fail-closed PM-01 error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class PublishPackageResult:
    run: ContentRun
    artifact: Artifact
    content_version: ContentVersion
    experiment: ContentExperiment
    replayed: bool


@dataclass(frozen=True, slots=True)
class PublishDecisionResult:
    run: ContentRun
    approval: Approval
    package: Artifact
    replayed: bool


@dataclass(frozen=True, slots=True)
class PublishDispatch:
    run: ContentRun
    step: StepRun
    job: Job
    intent: OutboxIntent
    package: Artifact
    approval: Approval
    replayed: bool


@dataclass(frozen=True, slots=True)
class PreparedWordPressCall:
    dispatch: PublishDispatch
    request: WordPressWriteRequest


@dataclass(frozen=True, slots=True)
class WordPressWriteRequest:
    idempotency_key: str
    action: PublishAction
    slug: str
    title: str
    body_markdown: str
    excerpt: str
    locale: str
    content_type: str
    metadata: dict[str, object]
    expected_external_id: str | None
    expected_external_revision_id: str | None


@dataclass(frozen=True, slots=True)
class WordPressWriteResult:
    outcome: Literal["confirmed_success", "unknown"]
    external_id: str | None = None
    canonical_url: str | None = None
    external_revision_id: str | None = None
    external_status: str | None = None
    published_at: datetime | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class WordPressReconciliation:
    outcome: WordPressReconcileOutcome
    external_id: str | None = None
    canonical_url: str | None = None
    external_revision_id: str | None = None
    external_status: str | None = None
    published_at: datetime | None = None
    message: str | None = None


class WordPressGateway(Protocol):
    """Injected transport seam; PM-01 itself does not activate credentials/network."""

    async def execute(self, request: WordPressWriteRequest) -> WordPressWriteResult: ...

    async def reconcile(
        self,
        request: WordPressWriteRequest,
    ) -> WordPressReconciliation: ...


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ref(artifact: Artifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublishError(code)
    return value.strip()


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PublishError(code)
    return cast(dict[str, object], value)


def _list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise PublishError(code)
    return list(value)


def _journal_body(draft: dict[str, object]) -> str:
    parts = [_text(draft.get("lead_markdown"), "publish_lead_missing")]
    for raw in _list(draft.get("sections"), "publish_sections_invalid"):
        section = _dict(raw, "publish_section_invalid")
        heading = _text(section.get("heading"), "publish_section_heading_missing")
        body = _text(section.get("body_markdown"), "publish_section_body_missing")
        parts.append(f"## {heading}\n\n{body}")
    parts.append(_text(draft.get("closing_markdown"), "publish_closing_missing"))
    return "\n\n".join(parts)


async def _approved_lineage(
    session: AsyncSession,
    *,
    content_version_id: UUID,
    experiment_id: UUID,
) -> tuple[
    ContentVersion,
    ContentItem,
    ContentCase,
    LocaleVariant,
    ContentRun,
    Artifact,
    Approval,
    ContentExperiment,
    ContentOpportunity,
    NeedHypothesis,
]:
    version = await session.get(ContentVersion, content_version_id)
    if version is None or version.status not in {"approved", "published"}:
        raise PublishError("publish_content_version_not_approved")
    if version.final_artifact_id is None or version.created_by_run_id is None:
        raise PublishError("publish_content_version_lineage_missing")

    item = await session.get(ContentItem, version.content_item_id)
    final_artifact = await session.get(Artifact, version.final_artifact_id)
    source_run = await session.get(ContentRun, version.created_by_run_id)
    if item is None or final_artifact is None or source_run is None:
        raise PublishError("publish_content_version_lineage_missing")
    if (
        source_run.run_mode == "eval"
        or source_run.content_item_id != item.id
        or final_artifact.run_id != source_run.id
        or final_artifact.artifact_type != "final_content"
        or final_artifact.content_json != version.content_json
        or final_artifact.content_hash != _hash(final_artifact.content_json)
        or _hash(version.content_json) != final_artifact.content_hash
    ):
        raise PublishError("publish_content_version_lineage_mismatch")

    case = await session.get(ContentCase, item.content_case_id)
    variant = await session.get(LocaleVariant, item.locale_variant_id)
    if item.content_type != "journal":
        raise PublishError("publish_content_type_unsupported")
    if (
        case is None
        or variant is None
        or case.id != source_run.content_case_id
        or variant.id != source_run.locale_variant_id
        or variant.content_case_id != case.id
        or item.project_id != case.project_id
    ):
        raise PublishError("publish_content_identity_mismatch")

    approvals = list(
        (
            await session.scalars(
                select(Approval).where(
                    Approval.run_id == source_run.id,
                    Approval.step_key == "final_review",
                    Approval.artifact_id == final_artifact.id,
                    Approval.decision == "approved",
                )
            )
        ).all()
    )
    if len(approvals) != 1:
        raise PublishError("publish_final_approval_missing")
    approval = approvals[0]
    checkpoint = await get_latest_checkpoint(session, run_id=source_run.id)
    checkpoint_payload = checkpoint.content_json if checkpoint is not None else None
    approval_ids = (
        checkpoint_payload.get("approval_ids")
        if isinstance(checkpoint_payload, dict)
        else None
    )
    if (
        source_run.status != "completed"
        or not isinstance(approval_ids, list)
        or str(approval.id) not in approval_ids
        or checkpoint_payload.get("pending_approval") is not None
    ):
        raise PublishError("publish_final_approval_history_invalid")

    experiment = await session.get(ContentExperiment, experiment_id)
    opportunity = await session.get(ContentOpportunity, case.content_opportunity_id)
    need = await session.get(NeedHypothesis, case.need_hypothesis_id)
    if (
        experiment is None
        or opportunity is None
        or need is None
        or experiment.project_id != case.project_id
        or experiment.content_opportunity_id != opportunity.id
        or experiment.need_hypothesis_id != need.id
        or experiment.hypothesis_version != need.version
        or opportunity.need_hypothesis_id != need.id
        or experiment.status not in {"PLANNED", "RUNNING"}
        or not experiment.expected_behaviour.strip()
        or not experiment.measurement_plan_json
        or not experiment.metric_definitions_json
        or not experiment.minimum_evidence_json
        or experiment.review_window_start is None
        or experiment.review_window_end is None
        or experiment.review_window_end < experiment.review_window_start
    ):
        raise PublishError("publish_experiment_not_ready")
    if experiment.content_item_id not in {None, item.id}:
        raise PublishError("publish_experiment_content_item_conflict")
    if experiment.content_version_id not in {None, version.id}:
        raise PublishError("publish_experiment_content_version_conflict")

    return (
        version,
        item,
        case,
        variant,
        source_run,
        final_artifact,
        approval,
        experiment,
        opportunity,
        need,
    )


async def _quality_refs(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
    final_artifact_id: UUID,
) -> dict[str, object]:
    progress = await get_quality_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=None,
    )
    if progress is None:
        raise PublishError("publish_quality_progress_missing")
    lanes = [
        lane
        for lane in progress.lanes
        if lane.writer.locale_variant is not None
        and lane.writer.locale_variant.id == locale_variant_id
    ]
    if len(lanes) != 1:
        raise PublishError("publish_quality_lane_ambiguous")
    lane = lanes[0]
    if (
        lane.final_content is None
        or lane.final_content.id != final_artifact_id
        or lane.audit.artifact is None
        or lane.audit.evaluation is None
        or lane.source_copy.artifact is None
        or lane.source_copy.evaluation is None
        or lane.reader_value.artifact is None
        or lane.reader_value.evaluation is None
        or lane.search_ai.artifact is None
        or lane.search_ai.evaluation is None
        or lane.audit.evaluation.result == "fail"
        or lane.source_copy.evaluation.result == "fail"
        or lane.reader_value.evaluation.result == "fail"
        or lane.search_ai.evaluation.result == "fail"
    ):
        raise PublishError("publish_quality_gate_not_satisfied")
    return {
        "assertion_audit": {
            "artifact": _ref(lane.audit.artifact),
            "evaluation_id": str(lane.audit.evaluation.id),
            "result": lane.audit.evaluation.result,
        },
        "source_copy": {
            "artifact": _ref(lane.source_copy.artifact),
            "evaluation_id": str(lane.source_copy.evaluation.id),
            "result": lane.source_copy.evaluation.result,
        },
        "reader_value": {
            "artifact": _ref(lane.reader_value.artifact),
            "evaluation_id": str(lane.reader_value.evaluation.id),
            "result": lane.reader_value.evaluation.result,
        },
        "search_ai": {
            "artifact": _ref(lane.search_ai.artifact),
            "evaluation_id": str(lane.search_ai.evaluation.id),
            "result": lane.search_ai.evaluation.result,
        },
    }


async def _lens_ref(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
    locale: str,
) -> dict[str, object] | None:
    rows = list(
        (
            await session.scalars(
                select(Artifact)
                .join(ContentRun, ContentRun.id == Artifact.run_id)
                .where(
                    ContentRun.content_case_id == content_case_id,
                    ContentRun.locale_variant_id == locale_variant_id,
                    Artifact.artifact_type == "lens_selection",
                    Artifact.locale == locale,
                )
                .order_by(
                    Artifact.created_at.desc(),
                    Artifact.version.desc(),
                    Artifact.id.desc(),
                )
            )
        ).all()
    )
    if not rows:
        return None
    artifact = rows[0]
    if not isinstance(artifact.content_json, dict) or artifact.content_hash != _hash(
        artifact.content_json
    ):
        raise PublishError("publish_lens_selection_invalid")
    run_ref = artifact.content_json.get("run_ref")
    if not isinstance(run_ref, dict):
        raise PublishError("publish_lens_selection_invalid")
    if (
        run_ref.get("content_case_id") != str(content_case_id)
        or run_ref.get("locale_variant_id") != str(locale_variant_id)
        or run_ref.get("locale") != locale
    ):
        raise PublishError("publish_lens_selection_identity_mismatch")
    primary = artifact.content_json.get("primary_lens")
    if primary is not None and (not isinstance(primary, str) or not primary.strip()):
        raise PublishError("publish_lens_selection_invalid")
    return {
        "artifact": _ref(artifact),
        "primary_lens": primary,
        "merged_lenses": list(
            cast(list[object], artifact.content_json.get("merged_lenses", []))
        ),
    }


async def _evidence_context(
    session: AsyncSession,
    *,
    source_run_id: UUID,
) -> dict[str, object]:
    manifest = await session.scalar(
        select(ContextManifest)
        .where(ContextManifest.run_id == source_run_id)
        .order_by(ContextManifest.created_at.desc(), ContextManifest.id.desc())
        .limit(1)
    )
    if manifest is None:
        raise PublishError("publish_context_manifest_missing")
    return {
        "context_manifest_id": str(manifest.id),
        "evidence_set_id": (
            str(manifest.evidence_set_id) if manifest.evidence_set_id is not None else None
        ),
        "originality_pack_id": (
            str(manifest.originality_pack_id)
            if manifest.originality_pack_id is not None
            else None
        ),
    }


async def _journey_stages(
    session: AsyncSession,
    *,
    content_item_id: UUID,
) -> list[str]:
    values = list(
        (
            await session.scalars(
                select(ContentItemJourneyStage.stage_key)
                .where(ContentItemJourneyStage.content_item_id == content_item_id)
                .order_by(ContentItemJourneyStage.stage_key)
            )
        ).all()
    )
    return values


def _package_content(
    *,
    version: ContentVersion,
    item: ContentItem,
    case: ContentCase,
    variant: LocaleVariant,
    final_artifact: Artifact,
    final_approval: Approval,
    experiment: ContentExperiment,
    opportunity: ContentOpportunity,
    need: NeedHypothesis,
    quality: dict[str, object],
    lens: dict[str, object] | None,
    evidence_context: dict[str, object],
    journey_stages: list[str],
    target: str,
    action: PublishAction,
    slug: str,
) -> dict[str, object]:
    wrapper = _dict(version.content_json, "publish_content_payload_invalid")
    draft = _dict(wrapper.get("draft"), "publish_content_draft_invalid")
    if draft.get("locale") != variant.locale:
        raise PublishError("publish_content_locale_mismatch")
    title = _text(draft.get("title"), "publish_title_missing")
    standfirst = _text(draft.get("standfirst"), "publish_standfirst_missing")
    body = _journal_body(draft)
    return {
        "schema_version": PUBLISH_PACKAGE_SCHEMA_VERSION,
        "artifact_type": PUBLISH_PACKAGE_ARTIFACT_TYPE,
        "identity": {
            "project_id": str(case.project_id),
            "content_case_id": str(case.id),
            "locale_variant_id": str(variant.id),
            "content_item_id": str(item.id),
            "content_version_id": str(version.id),
            "content_version_no": version.version_no,
            "content_opportunity_id": str(opportunity.id),
            "need_hypothesis_id": str(need.id),
            "need_hypothesis_version": need.version,
            "audience_hypothesis_id": (
                str(case.audience_hypothesis_id)
                if case.audience_hypothesis_id is not None
                else None
            ),
            "content_experiment_id": str(experiment.id),
            "content_hypothesis": case.content_hypothesis,
            "journey_stages": journey_stages,
            "lens_selection": lens,
        },
        "publish_target": {
            "target": target,
            "action": action,
            "slug": slug,
        },
        "content": {
            "content_type": item.content_type,
            "locale": variant.locale,
            "title": title,
            "body_markdown": body,
            "excerpt": standfirst,
            "canonical_entities": [],
            "internal_links": list(
                cast(list[object], draft.get("internal_link_intents", []))
            ),
            "media_references": [],
            "structured_data_recommendation": {
                "type": "Article" if item.content_type == "journal" else "VisualArtwork",
                "status": "recommendation_only",
            },
        },
        "lineage": {
            "final_artifact": _ref(final_artifact),
            "final_approval": {
                "id": str(final_approval.id),
                "actor_id": final_approval.actor_id,
                "decision": final_approval.decision,
            },
            "quality": quality,
            "evidence_context": evidence_context,
        },
        "measurement": {
            "expected_behaviour": experiment.expected_behaviour,
            "measurement_plan": list(experiment.measurement_plan_json),
            "metric_definitions": list(experiment.metric_definitions_json),
            "minimum_evidence": list(experiment.minimum_evidence_json),
            "review_window_start": (
                experiment.review_window_start.isoformat()
                if experiment.review_window_start is not None
                else None
            ),
            "review_window_end": (
                experiment.review_window_end.isoformat()
                if experiment.review_window_end is not None
                else None
            ),
        },
    }


async def prepare_publish_package(
    session: AsyncSession,
    *,
    content_version_id: UUID,
    experiment_id: UUID,
    slug: str,
    action: PublishAction = "draft",
    target: str = "wordpress",
) -> PublishPackageResult:
    """Create/reuse one exact package and pause at a separate publish authorization."""

    normalized_slug = slug.strip().lower()
    if not _SLUG_RE.fullmatch(normalized_slug):
        raise PublishError("publish_slug_invalid")
    if target != "wordpress" or action not in {"draft", "publish"}:
        raise PublishError("publish_target_action_invalid")

    (
        version,
        item,
        case,
        variant,
        source_run,
        final_artifact,
        final_approval,
        experiment,
        opportunity,
        need,
    ) = await _approved_lineage(
        session,
        content_version_id=content_version_id,
        experiment_id=experiment_id,
    )
    quality = await _quality_refs(
        session,
        content_case_id=case.id,
        locale_variant_id=variant.id,
        final_artifact_id=final_artifact.id,
    )
    package_payload = _package_content(
        version=version,
        item=item,
        case=case,
        variant=variant,
        final_artifact=final_artifact,
        final_approval=final_approval,
        experiment=experiment,
        opportunity=opportunity,
        need=need,
        quality=quality,
        lens=await _lens_ref(
            session,
            content_case_id=case.id,
            locale_variant_id=variant.id,
            locale=variant.locale,
        ),
        evidence_context=await _evidence_context(
            session,
            source_run_id=source_run.id,
        ),
        journey_stages=await _journey_stages(
            session,
            content_item_id=item.id,
        ),
        target=target,
        action=action,
        slug=normalized_slug,
    )
    package_hash = _hash(package_payload)

    existing_packages = list(
        (
            await session.scalars(
                select(Artifact)
                .join(ContentRun, ContentRun.id == Artifact.run_id)
                .where(
                    ContentRun.run_mode == "publish",
                    ContentRun.content_item_id == item.id,
                    Artifact.artifact_type == PUBLISH_PACKAGE_ARTIFACT_TYPE,
                    Artifact.content_hash == package_hash,
                )
                .order_by(Artifact.created_at.desc(), Artifact.id.desc())
            )
        ).all()
    )
    reusable: list[tuple[Artifact, ContentRun]] = []
    for existing in existing_packages:
        run = await session.get(ContentRun, existing.run_id)
        if run is None or existing.content_json != package_payload:
            raise PublishError("publish_package_replay_conflict")
        if run.status in {"waiting_approval", "running", "completed"}:
            reusable.append((existing, run))
    if len(reusable) > 1:
        raise PublishError("publish_package_active_duplicate")
    if reusable:
        artifact, run = reusable[0]
        return PublishPackageResult(
            run=run,
            artifact=artifact,
            content_version=version,
            experiment=experiment,
            replayed=True,
        )

    publish_run = ContentRun(
        project_id=item.project_id,
        content_case_id=case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="publish",
        status="running",
        current_step=PUBLISH_AUTHORIZATION_STEP,
        settings_snapshot_id=source_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(publish_run)
    await session.flush()

    artifact = Artifact(
        run_id=publish_run.id,
        step_run_id=None,
        artifact_type=PUBLISH_PACKAGE_ARTIFACT_TYPE,
        locale=variant.locale,
        version=1,
        content_json=package_payload,
        content_hash=package_hash,
    )
    session.add(artifact)
    await session.flush()
    await pause_for_approval(
        session,
        run_id=publish_run.id,
        step_key=PUBLISH_AUTHORIZATION_STEP,
        artifact_id=artifact.id,
    )
    await session.refresh(publish_run)
    return PublishPackageResult(
        run=publish_run,
        artifact=artifact,
        content_version=version,
        experiment=experiment,
        replayed=False,
    )


async def submit_publish_decision(
    session: AsyncSession,
    *,
    publish_run_id: UUID,
    package_artifact_id: UUID,
    decision: PublishDecision,
    actor_id: str,
    comment: str | None = None,
) -> PublishDecisionResult:
    """Persist the separate Founder publish authorization; never dispatch implicitly."""

    if not actor_id.strip():
        raise PublishError("publish_approval_actor_required")
    run = await session.get(ContentRun, publish_run_id)
    package = await session.get(Artifact, package_artifact_id)
    if (
        run is None
        or run.run_mode != "publish"
        or package is None
        or package.run_id != run.id
        or package.artifact_type != PUBLISH_PACKAGE_ARTIFACT_TYPE
        or package.content_hash != _hash(package.content_json)
    ):
        raise PublishError("publish_approval_binding_invalid")

    rows = list(
        (
            await session.scalars(
                select(Approval).where(
                    Approval.run_id == run.id,
                    Approval.step_key == PUBLISH_AUTHORIZATION_STEP,
                    Approval.artifact_id == package.id,
                )
            )
        ).all()
    )
    if rows:
        if len(rows) != 1 or rows[0].decision != decision or rows[0].actor_id != actor_id.strip():
            raise PublishError("publish_approval_replay_conflict")
        return PublishDecisionResult(
            run=run,
            approval=rows[0],
            package=package,
            replayed=True,
        )

    if run.status != "waiting_approval":
        raise PublishError("publish_approval_state_invalid")
    approval = await resolve_approval(
        session,
        run_id=run.id,
        step_key=PUBLISH_AUTHORIZATION_STEP,
        artifact_id=package.id,
        decision=decision,
        actor_id=actor_id.strip(),
        comment=comment.strip() if isinstance(comment, str) and comment.strip() else None,
    )
    await session.refresh(run)
    return PublishDecisionResult(
        run=run,
        approval=approval,
        package=package,
        replayed=False,
    )


def _package_identity(
    package: Artifact,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    payload = _dict(package.content_json, "publish_package_payload_invalid")
    if package.content_hash != _hash(payload):
        raise PublishError("publish_package_hash_mismatch")
    return (
        _dict(payload.get("identity"), "publish_package_identity_invalid"),
        _dict(payload.get("publish_target"), "publish_package_target_invalid"),
        _dict(payload.get("content"), "publish_package_content_invalid"),
    )


def _idempotency_key(
    *,
    content_item_id: str,
    content_version_id: str,
    target: str,
    action: str,
    package_hash: str,
) -> str:
    raw = f"{content_item_id}:{content_version_id}:{target}:{action}:{package_hash}"
    return f"pm01:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


async def prepare_wordpress_dispatch(
    session: AsyncSession,
    *,
    publish_run_id: UUID,
    package_artifact_id: UUID,
) -> PublishDispatch:
    """Create/reuse the durable outbox intent and job after explicit authorization."""

    run = await session.get(ContentRun, publish_run_id)
    package = await session.get(Artifact, package_artifact_id)
    if (
        run is None
        or run.run_mode != "publish"
        or run.status != "running"
        or package is None
        or package.run_id != run.id
    ):
        raise PublishError("publish_dispatch_state_invalid")
    identity, target, _content = _package_identity(package)
    if target.get("target") != "wordpress":
        raise PublishError("publish_dispatch_target_invalid")

    approvals = list(
        (
            await session.scalars(
                select(Approval).where(
                    Approval.run_id == run.id,
                    Approval.step_key == PUBLISH_AUTHORIZATION_STEP,
                    Approval.artifact_id == package.id,
                    Approval.decision == "approved",
                )
            )
        ).all()
    )
    if len(approvals) != 1:
        raise PublishError("publish_authorization_missing")
    approval = approvals[0]
    checkpoint = await get_latest_checkpoint(session, run_id=run.id)
    checkpoint_payload = checkpoint.content_json if checkpoint is not None else None
    approval_ids = (
        checkpoint_payload.get("approval_ids")
        if isinstance(checkpoint_payload, dict)
        else None
    )
    if (
        not isinstance(approval_ids, list)
        or str(approval.id) not in approval_ids
        or checkpoint_payload.get("pending_approval") is not None
    ):
        raise PublishError("publish_authorization_history_invalid")

    item_id = _text(identity.get("content_item_id"), "publish_item_ref_invalid")
    version_id = _text(identity.get("content_version_id"), "publish_version_ref_invalid")
    action = _text(target.get("action"), "publish_action_invalid")
    key = _idempotency_key(
        content_item_id=item_id,
        content_version_id=version_id,
        target="wordpress",
        action=action,
        package_hash=package.content_hash,
    )
    intent = await create_outbox_intent(
        session,
        run_id=run.id,
        intent_type="wordpress_publish",
        idempotency_key=key,
        payload_ref=f"artifact://{package.id}/{package.content_hash}",
    )

    step = await session.scalar(
        select(StepRun).where(
            StepRun.run_id == run.id,
            StepRun.step_key == WORDPRESS_STEP,
        )
    )
    replayed = step is not None
    if step is None:
        step = StepRun(
            run_id=run.id,
            step_key=WORDPRESS_STEP,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[str(package.id), str(intent.id), str(approval.id)],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
    elif step.input_artifact_refs_json != [
        str(package.id),
        str(intent.id),
        str(approval.id),
    ]:
        raise PublishError("publish_dispatch_step_conflict")

    job = await enqueue_job(
        session,
        run_id=run.id,
        step_run_id=step.id,
        dedupe_key=f"wordpress:{key}",
    )
    return PublishDispatch(
        run=run,
        step=step,
        job=job,
        intent=intent,
        package=package,
        approval=approval,
        replayed=replayed,
    )


async def _request_for_package(
    session: AsyncSession,
    *,
    package: Artifact,
    intent: OutboxIntent,
) -> WordPressWriteRequest:
    identity, target, content = _package_identity(package)
    try:
        item_id = UUID(_text(identity.get("content_item_id"), "publish_item_ref_invalid"))
    except ValueError as exc:
        raise PublishError("publish_item_ref_invalid") from exc
    mapping = await session.scalar(
        select(PublishedContent).where(
            PublishedContent.content_item_id == item_id,
            PublishedContent.target == "wordpress",
        )
    )
    raw_action = _text(target.get("action"), "publish_action_invalid")
    if raw_action not in {"draft", "publish"}:
        raise PublishError("publish_action_invalid")
    if (
        mapping is not None
        and mapping.external_status == "publish"
        and raw_action == "draft"
    ):
        raise PublishError("publish_live_post_draft_overwrite_forbidden")
    metadata = {
        "contentengine": {
            "content_item_id": str(item_id),
            "content_version_id": _text(
                identity.get("content_version_id"),
                "publish_version_ref_invalid",
            ),
            "publish_package_hash": package.content_hash,
            "idempotency_key": intent.idempotency_key,
        },
        "structured_data_recommendation": content.get(
            "structured_data_recommendation"
        ),
        "internal_links": content.get("internal_links", []),
        "canonical_entities": content.get("canonical_entities", []),
        "media_references": content.get("media_references", []),
    }
    return WordPressWriteRequest(
        idempotency_key=intent.idempotency_key,
        action=cast(PublishAction, raw_action),
        slug=_text(target.get("slug"), "publish_slug_invalid"),
        title=_text(content.get("title"), "publish_title_missing"),
        body_markdown=_text(content.get("body_markdown"), "publish_body_missing"),
        excerpt=_text(content.get("excerpt"), "publish_excerpt_missing"),
        locale=_text(content.get("locale"), "publish_locale_missing"),
        content_type=_text(content.get("content_type"), "publish_content_type_missing"),
        metadata=metadata,
        expected_external_id=mapping.external_id if mapping is not None else None,
        expected_external_revision_id=(
            mapping.external_revision_id if mapping is not None else None
        ),
    )


def _validated_success(
    *,
    result: WordPressWriteResult | WordPressReconciliation,
) -> tuple[str, str, str | None, str, datetime | None]:
    if result.outcome != "confirmed_success":
        raise PublishError("publish_external_result_not_success")
    external_id = _text(result.external_id, "publish_external_id_missing")
    url = _text(result.canonical_url, "publish_canonical_url_missing")
    status = _text(result.external_status, "publish_external_status_missing")
    if status not in {"draft", "publish", "future", "private"}:
        raise PublishError("publish_external_status_invalid")
    revision = result.external_revision_id.strip() if isinstance(
        result.external_revision_id, str
    ) and result.external_revision_id.strip() else None
    published_at = result.published_at
    if status == "publish" and published_at is None:
        raise PublishError("publish_external_timestamp_missing")
    return external_id, url, revision, status, published_at


def _require_requested_external_state(
    *,
    package: Artifact,
    result: WordPressWriteResult | WordPressReconciliation,
) -> None:
    _identity, target, _content = _package_identity(package)
    action = _text(target.get("action"), "publish_action_invalid")
    expected_status = "draft" if action == "draft" else "publish"
    if result.external_status != expected_status:
        raise PublishError("publish_external_status_mismatch")


async def _finalize_confirmed_publish(
    session: AsyncSession,
    *,
    dispatch: PublishDispatch,
    result: WordPressWriteResult | WordPressReconciliation,
) -> tuple[PublishedContent, PublishEvent]:
    external_id, url, revision, status, published_at = _validated_success(result=result)
    identity, target, _content = _package_identity(dispatch.package)
    try:
        item_id = UUID(_text(identity.get("content_item_id"), "publish_item_ref_invalid"))
        version_id = UUID(
            _text(identity.get("content_version_id"), "publish_version_ref_invalid")
        )
        experiment_id = UUID(
            _text(identity.get("content_experiment_id"), "publish_experiment_ref_invalid")
        )
    except ValueError as exc:
        raise PublishError("publish_identity_uuid_invalid") from exc

    item = await session.get(ContentItem, item_id)
    version = await session.get(ContentVersion, version_id)
    experiment = await session.get(ContentExperiment, experiment_id)
    if (
        item is None
        or version is None
        or experiment is None
        or version.content_item_id != item.id
        or item.id != dispatch.run.content_item_id
    ):
        raise PublishError("publish_identity_mismatch")

    mapping = await session.scalar(
        select(PublishedContent)
        .where(
            PublishedContent.project_id == item.project_id,
            PublishedContent.content_item_id == item.id,
            PublishedContent.target == "wordpress",
        )
        .with_for_update()
    )
    mapping_existed = mapping is not None
    if mapping is None:
        mapping = PublishedContent(
            project_id=item.project_id,
            content_item_id=item.id,
            target="wordpress",
            external_id=external_id,
            canonical_url=url,
            current_content_version_id=version.id,
            external_revision_id=revision,
            external_status=status,
            published_at=published_at if status == "publish" else None,
        )
        session.add(mapping)
        await session.flush()
    else:
        if mapping.external_id != external_id:
            raise PublishError("publish_external_mapping_conflict")
        mapping.canonical_url = url
        mapping.current_content_version_id = version.id
        mapping.external_revision_id = revision
        mapping.external_status = status
        mapping.published_at = published_at if status == "publish" else None
        await session.flush()

    action = _text(target.get("action"), "publish_action_invalid")
    event_action = f"update_{action}" if mapping_existed else action
    existing_event = await session.scalar(
        select(PublishEvent).where(
            PublishEvent.outbox_intent_id == dispatch.intent.id
        )
    )
    if existing_event is not None:
        if (
            existing_event.published_content_id != mapping.id
            or existing_event.content_version_id != version.id
            or existing_event.idempotency_key != dispatch.intent.idempotency_key
        ):
            raise PublishError("publish_event_replay_conflict")
        return mapping, existing_event

    event = PublishEvent(
        published_content_id=mapping.id,
        content_version_id=version.id,
        publish_package_artifact_id=dispatch.package.id,
        publish_approval_id=dispatch.approval.id,
        outbox_intent_id=dispatch.intent.id,
        idempotency_key=dispatch.intent.idempotency_key,
        action=event_action,
        external_revision_id=revision,
        external_status=status,
        canonical_url=url,
        published_at=published_at if status == "publish" else None,
        result_json={
            "external_id": external_id,
            "external_revision_id": revision,
            "external_status": status,
            "canonical_url": url,
        },
    )
    session.add(event)

    experiment.content_item_id = item.id
    experiment.content_version_id = version.id
    experiment.published_content_id = mapping.id
    if status == "publish":
        experiment.status = "RUNNING"
        version.status = "published"
        item.status = "published"
        previous = list(
            (
                await session.scalars(
                    select(ContentVersion).where(
                        ContentVersion.content_item_id == item.id,
                        ContentVersion.id != version.id,
                        ContentVersion.status == "published",
                    )
                )
            ).all()
        )
        for row in previous:
            row.status = "superseded"
    await session.flush()
    return mapping, event


async def _bound_dispatch_from_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
) -> PublishDispatch:
    job = await session.get(Job, job_id)
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= utc_now()
    ):
        raise PublishError("publish_job_lease_invalid")
    step = await session.get(StepRun, job.step_run_id)
    run = await session.get(ContentRun, job.run_id)
    if (
        step is None
        or run is None
        or step.run_id != run.id
        or step.step_key != WORDPRESS_STEP
        or len(step.input_artifact_refs_json) != 3
    ):
        raise PublishError("publish_job_binding_invalid")
    try:
        package_id = UUID(step.input_artifact_refs_json[0])
        intent_id = UUID(step.input_artifact_refs_json[1])
        approval_id = UUID(step.input_artifact_refs_json[2])
    except ValueError as exc:
        raise PublishError("publish_job_binding_invalid") from exc
    package = await session.get(Artifact, package_id)
    intent = await session.get(OutboxIntent, intent_id)
    approval = await session.get(Approval, approval_id)
    if (
        package is None
        or intent is None
        or approval is None
        or package.run_id != run.id
        or intent.run_id != run.id
        or approval.run_id != run.id
        or approval.artifact_id != package.id
        or approval.step_key != PUBLISH_AUTHORIZATION_STEP
        or approval.decision != "approved"
    ):
        raise PublishError("publish_job_binding_invalid")
    return PublishDispatch(
        run=run,
        step=step,
        job=job,
        intent=intent,
        package=package,
        approval=approval,
        replayed=False,
    )


async def begin_wordpress_dispatch(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
) -> PreparedWordPressCall:
    """Move the durable intent to processing before any external request.

    The caller MUST commit this DB transaction before calling WordPress. The returned
    request contains only the bounded external payload. This phase never performs
    network I/O.
    """

    dispatch = await _bound_dispatch_from_job(
        session,
        job_id=job_id,
        worker_id=worker_id,
    )
    request = await _request_for_package(
        session,
        package=dispatch.package,
        intent=dispatch.intent,
    )
    processing = await prepare_outbox_dispatch(
        session,
        intent_id=dispatch.intent.id,
        job_id=dispatch.job.id,
        worker_id=worker_id,
    )
    dispatch.run.current_step = WORDPRESS_STEP
    await session.flush()
    return PreparedWordPressCall(
        dispatch=PublishDispatch(
            run=dispatch.run,
            step=dispatch.step,
            job=dispatch.job,
            intent=processing,
            package=dispatch.package,
            approval=dispatch.approval,
            replayed=dispatch.replayed,
        ),
        request=request,
    )


async def execute_wordpress_call(
    *,
    gateway: WordPressGateway,
    request: WordPressWriteRequest,
) -> WordPressWriteResult:
    """External-only phase. Call only after begin_wordpress_dispatch is committed."""

    return await gateway.execute(request)


async def record_wordpress_execution_result(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    result: WordPressWriteResult,
) -> tuple[PublishedContent | None, PublishEvent | None]:
    """Persist the external result after the network phase completed."""

    dispatch = await _bound_dispatch_from_job(
        session,
        job_id=job_id,
        worker_id=worker_id,
    )
    if dispatch.intent.status != "processing":
        raise PublishError("publish_outbox_not_processing")

    if result.outcome == "unknown":
        await mark_outbox_needs_reconciliation(
            session,
            intent_id=dispatch.intent.id,
            job_id=dispatch.job.id,
            worker_id=worker_id,
            error_class="ambiguous_side_effect",
            message=result.message or "WordPress outcome unknown",
        )
        return None, None

    external_id, _url, _revision, _status, _published_at = _validated_success(
        result=result
    )
    _require_requested_external_state(
        package=dispatch.package,
        result=result,
    )
    await complete_outbox_intent(
        session,
        intent_id=dispatch.intent.id,
        job_id=dispatch.job.id,
        worker_id=worker_id,
        result=SideEffectExecutionResult(
            external_ref=f"wordpress://post/{external_id}"
        ),
    )
    mapping, event = await _finalize_confirmed_publish(
        session,
        dispatch=dispatch,
        result=result,
    )
    await complete_job(
        session,
        job_id=dispatch.job.id,
        worker_id=worker_id,
    )
    if dispatch.run.status == "running":
        await transition_run(
            session,
            run_id=dispatch.run.id,
            status="completed",
        )
    return mapping, event


async def prepare_wordpress_reconciliation(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
) -> PreparedWordPressCall:
    """Build a read-only reconciliation request; never resend the write."""

    dispatch = await _bound_dispatch_from_job(
        session,
        job_id=job_id,
        worker_id=worker_id,
    )
    if dispatch.intent.status not in {"processing", "needs_reconciliation"}:
        raise PublishError("publish_reconciliation_not_required")
    request = await _request_for_package(
        session,
        package=dispatch.package,
        intent=dispatch.intent,
    )
    return PreparedWordPressCall(dispatch=dispatch, request=request)


async def execute_wordpress_reconciliation(
    *,
    gateway: WordPressGateway,
    request: WordPressWriteRequest,
) -> WordPressReconciliation:
    """External-only reconciliation phase. It MUST NOT write/resend the post."""

    return await gateway.reconcile(request)


async def record_wordpress_reconciliation(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    result: WordPressReconciliation,
) -> tuple[str, PublishedContent | None, PublishEvent | None]:
    """Apply reconciliation before any possible resend."""

    dispatch = await _bound_dispatch_from_job(
        session,
        job_id=job_id,
        worker_id=worker_id,
    )
    outbox_result = ReconciliationResult(
        outcome=result.outcome,
        external_ref=(
            f"wordpress://post/{result.external_id}"
            if result.outcome == "confirmed_success" and result.external_id
            else None
        ),
        message=result.message,
    )
    await apply_reconciliation_result(
        session,
        intent_id=dispatch.intent.id,
        job_id=dispatch.job.id,
        worker_id=worker_id,
        result=outbox_result,
    )
    if result.outcome == "confirmed_absent":
        return result.outcome, None, None
    if result.outcome == "unknown":
        return result.outcome, None, None
    if result.outcome == "conflict":
        await fail_job_and_maybe_retry(
            session,
            job_id=dispatch.job.id,
            worker_id=worker_id,
            failure_class="publish_conflict",
            message=result.message or "WordPress reconciliation conflict",
            retry_policy=RetryPolicy(max_step_attempts=1),
        )
        if dispatch.run.status == "running":
            await transition_run(
                session,
                run_id=dispatch.run.id,
                status="failed",
            )
        return result.outcome, None, None

    _require_requested_external_state(
        package=dispatch.package,
        result=result,
    )
    mapping, event = await _finalize_confirmed_publish(
        session,
        dispatch=dispatch,
        result=result,
    )
    await complete_job(
        session,
        job_id=dispatch.job.id,
        worker_id=worker_id,
    )
    if dispatch.run.status == "running":
        await transition_run(
            session,
            run_id=dispatch.run.id,
            status="completed",
        )
    return result.outcome, mapping, event


__all__ = [
    "PUBLISH_AUTHORIZATION_STEP",
    "PUBLISH_PACKAGE_ARTIFACT_TYPE",
    "WORDPRESS_STEP",
    "PublishDecisionResult",
    "PublishDispatch",
    "PublishError",
    "PublishPackageResult",
    "PreparedWordPressCall",
    "WordPressGateway",
    "WordPressReconciliation",
    "WordPressWriteRequest",
    "WordPressWriteResult",
    "begin_wordpress_dispatch",
    "execute_wordpress_call",
    "execute_wordpress_reconciliation",
    "prepare_publish_package",
    "prepare_wordpress_dispatch",
    "prepare_wordpress_reconciliation",
    "record_wordpress_execution_result",
    "record_wordpress_reconciliation",
    "submit_publish_decision",
]