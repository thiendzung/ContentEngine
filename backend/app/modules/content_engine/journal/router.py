from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.journal.context import JournalContextError, build_journal_context
from app.modules.content_engine.journal.operator_control import (
    OperatorCommandResult,
    OperatorControlError,
    OperatorState,
)
from app.modules.content_engine.journal.operator_creation import (
    OperatorCreateResult,
    create_journal_case_with_receipt,
)
from app.modules.content_engine.journal.operator_decisions import (
    OperatorDecisionResult,
    submit_operator_decision,
)
from app.modules.content_engine.journal.operator_manual_intake import (
    FounderJournalIntakeResult,
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_preflight import (
    build_journal_operator_preflight,
)
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_view import (
    OperatorCaseView,
    get_operator_case_view,
)
from app.modules.content_engine.journal.production_board import (
    ProductionBoardCase,
    list_production_board_cases,
)
from app.modules.content_engine.journal.review_action_view import (
    get_action_aware_review_case,
    list_action_aware_review_cases,
)
from app.modules.content_engine.journal.review_actions import (
    ReviewActionError,
    ReviewDecisionResult,
    submit_review_decision,
)
from app.modules.content_engine.journal.review_console import (
    ReviewCaseDetail,
    ReviewCaseSummary,
    ReviewConsoleError,
)
from app.modules.content_engine.models import ContentCase, ContentOpportunity, LocaleVariant

router = APIRouter(prefix="/journal", tags=["journal"])


class JournalVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    locale: str
    content_role: str
    primary_question: str
    primary_intent: str
    status: str


class JournalCaseResponse(BaseModel):
    id: UUID
    content_type: str
    status: str
    content_opportunity_id: UUID
    opportunity_question: str
    opportunity_decision: str
    opportunity_selected_by: str | None
    variants: list[JournalVariantResponse]


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    comment: str | None = None


class FounderJournalIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_slug: str = Field(default="motgu", min_length=1, max_length=100)
    source_locale: str = Field(min_length=1, max_length=32)
    research_country: str = Field(min_length=1, max_length=8)
    required_locales: list[str] = Field(
        default_factory=lambda: ["vi-VN", "en"],
        min_length=1,
    )
    content_role: Literal["pillar", "cluster"]
    reader: str = Field(min_length=1)
    situation: str = Field(min_length=1)
    need: str = Field(min_length=1)
    question: str = Field(min_length=1)
    intent: str = Field(min_length=1, max_length=64)
    promise: str = Field(min_length=1)
    coverage_requirements: list[str] = Field(min_length=1, max_length=12)
    selection_reason: str = Field(min_length=1)
    originality_material: str = Field(min_length=1)
    originality_writer_use: str = Field(min_length=1)
    originality_guardrails: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)


class OperatorCreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_opportunity_id: UUID
    expected_opportunity_version: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=200)


class OperatorCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["start", "continue", "resume", "retry", "cancel"]
    expected_state_version: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)
    knowledge_brief_id: UUID | None = None


class OperatorDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["angle", "outline", "final"]
    decision: Literal["approved", "changes_requested", "rejected"]
    expected_state_version: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)
    artifact_id: UUID | None = None
    artifact_version: int | None = Field(default=None, gt=0)
    artifact_hash: str | None = Field(default=None, min_length=64, max_length=64)
    selected_angle_id: str | None = None
    selected_candidate_hash: str | None = Field(default=None, min_length=64, max_length=64)
    locale_variant_id: UUID | None = None
    comment: str | None = None


def _operator_http_error(exc: OperatorControlError) -> HTTPException:
    not_found = {
        "operator_case_not_found",
        "operator_opportunity_not_found",
        "operator_project_not_found",
        "knowledge_brief_ref_not_found",
    }
    invalid = {
        "operator_idempotency_key_invalid",
        "operator_state_version_invalid",
        "operator_angle_binding_required",
        "operator_outline_binding_required",
        "operator_final_locale_required",
        "operator_required_locales_invalid",
        "operator_required_locales_duplicate",
        "operator_source_locale_not_required",
        "operator_source_locale_required",
        "operator_project_required",
        "operator_research_country_required",
        "operator_research_country_invalid",
        "operator_manual_content_role_invalid",
        "operator_manual_reader_required",
        "operator_manual_situation_required",
        "operator_manual_need_required",
        "operator_manual_question_required",
        "operator_manual_intent_required",
        "operator_manual_promise_required",
        "operator_manual_coverage_requirements_invalid",
        "operator_manual_coverage_requirement_required",
        "operator_manual_coverage_requirement_too_long",
        "operator_manual_coverage_requirement_duplicate",
        "operator_manual_selection_reason_required",
        "operator_manual_originality_material_required",
        "operator_manual_originality_writer_use_required",
        "operator_manual_originality_guardrails_required",
        "operator_knowledge_brief_binding_start_only",
        "operator_knowledge_brief_binding_stage_required",
    }
    if exc.code in not_found:
        status_code = 404
    elif exc.code in invalid:
        status_code = 422
    else:
        status_code = 409
    message = exc.detail or "Thao tác không hợp lệ hoặc trạng thái đã thay đổi."
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": message},
    )


@router.get("/content-cases", response_model=list[JournalCaseResponse])
async def list_journal_cases(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[JournalCaseResponse]:
    rows = (
        await session.execute(
            select(ContentCase, ContentOpportunity, LocaleVariant)
            .join(ContentOpportunity, ContentOpportunity.id == ContentCase.content_opportunity_id)
            .join(LocaleVariant, LocaleVariant.content_case_id == ContentCase.id)
            .where(ContentCase.content_type == "journal")
            .order_by(ContentCase.created_at, ContentCase.id, LocaleVariant.locale)
        )
    ).all()
    grouped: dict[UUID, JournalCaseResponse] = {}
    for content_case, opportunity, variant in rows:
        response = grouped.get(content_case.id)
        if response is None:
            response = JournalCaseResponse(
                id=content_case.id,
                content_type=content_case.content_type,
                status=content_case.status,
                content_opportunity_id=opportunity.id,
                opportunity_question=opportunity.question,
                opportunity_decision=opportunity.decision,
                opportunity_selected_by=opportunity.selected_by,
                variants=[],
            )
            grouped[content_case.id] = response
        response.variants.append(
            JournalVariantResponse(
                id=variant.id,
                locale=variant.locale,
                content_role=variant.content_role,
                primary_question=variant.primary_question,
                primary_intent=variant.primary_intent,
                status=variant.status,
            )
        )
    return list(grouped.values())


@router.get("/production-board", response_model=list[ProductionBoardCase])
async def list_journal_production_board(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ProductionBoardCase]:
    return await list_production_board_cases(session)


@router.get("/operator/preflight", response_model=dict[str, object])
async def get_journal_operator_preflight(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    return await build_journal_operator_preflight(session)


@router.post("/operator/intakes", response_model=FounderJournalIntakeResult)
async def create_journal_founder_intake(
    payload: FounderJournalIntakeRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> FounderJournalIntakeResult:
    try:
        async with session.begin():
            return await create_founder_journal_intake(
                session,
                project_slug=payload.project_slug,
                source_locale=payload.source_locale,
                research_country=payload.research_country,
                required_locales=payload.required_locales,
                content_role=payload.content_role,
                reader=payload.reader,
                situation=payload.situation,
                need=payload.need,
                question=payload.question,
                intent=payload.intent,
                promise=payload.promise,
                coverage_requirements=payload.coverage_requirements,
                selection_reason=payload.selection_reason,
                originality_material=payload.originality_material,
                originality_writer_use=payload.originality_writer_use,
                originality_guardrails=payload.originality_guardrails,
                idempotency_key=payload.idempotency_key,
                actor_id="founder",
            )
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.post("/operator/cases", response_model=OperatorCreateResult)
async def create_journal_operator_case(
    payload: OperatorCreateCaseRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OperatorCreateResult:
    try:
        async with session.begin():
            return await create_journal_case_with_receipt(
                session,
                content_opportunity_id=payload.content_opportunity_id,
                expected_opportunity_version=payload.expected_opportunity_version,
                idempotency_key=payload.idempotency_key,
                actor_id="founder",
            )
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.get("/operator/cases/{content_case_id}", response_model=OperatorState)
async def get_journal_operator_case(
    content_case_id: UUID,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OperatorState:
    try:
        return await get_operator_state(session, content_case_id=content_case_id)
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.get("/operator/cases/{content_case_id}/view", response_model=OperatorCaseView)
async def get_journal_operator_case_view(
    content_case_id: UUID,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OperatorCaseView:
    try:
        return await get_operator_case_view(session, content_case_id=content_case_id)
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.post(
    "/operator/cases/{content_case_id}/commands",
    response_model=OperatorCommandResult,
)
async def command_journal_operator_case(
    content_case_id: UUID,
    payload: OperatorCommandRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OperatorCommandResult:
    try:
        async with session.begin():
            return await submit_operator_command(
                session,
                content_case_id=content_case_id,
                intent=payload.intent,
                expected_state_version=payload.expected_state_version,
                idempotency_key=payload.idempotency_key,
                knowledge_brief_id=payload.knowledge_brief_id,
                actor_id="founder",
            )
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.post(
    "/operator/cases/{content_case_id}/decisions",
    response_model=OperatorDecisionResult,
)
async def decide_journal_operator_case(
    content_case_id: UUID,
    payload: OperatorDecisionRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OperatorDecisionResult:
    try:
        async with session.begin():
            return await submit_operator_decision(
                session,
                content_case_id=content_case_id,
                scope=payload.scope,
                decision=payload.decision,
                expected_state_version=payload.expected_state_version,
                idempotency_key=payload.idempotency_key,
                artifact_id=payload.artifact_id,
                artifact_version=payload.artifact_version,
                artifact_hash=payload.artifact_hash,
                selected_angle_id=payload.selected_angle_id,
                selected_candidate_hash=payload.selected_candidate_hash,
                locale_variant_id=payload.locale_variant_id,
                comment=payload.comment,
                actor_id="founder",
            )
    except OperatorControlError as exc:
        raise _operator_http_error(exc) from exc


@router.get("/review-cases", response_model=list[ReviewCaseSummary])
async def list_journal_review_cases(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ReviewCaseSummary]:
    return await list_action_aware_review_cases(session)


@router.get("/review-cases/{content_case_id}", response_model=ReviewCaseDetail)
async def get_journal_review_case(
    content_case_id: UUID,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReviewCaseDetail:
    try:
        return await get_action_aware_review_case(session, content_case_id=content_case_id)
    except ReviewConsoleError as exc:
        status_code = 404 if exc.code.endswith("not_found") else 422
        raise HTTPException(status_code=status_code, detail=exc.code) from exc


@router.post(
    "/review-cases/{content_case_id}/locales/{locale_variant_id}/decision",
    response_model=ReviewDecisionResult,
)
async def decide_journal_review_locale(
    content_case_id: UUID,
    locale_variant_id: UUID,
    payload: ReviewDecisionRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReviewDecisionResult:
    try:
        async with session.begin():
            return await submit_review_decision(
                session,
                content_case_id=content_case_id,
                locale_variant_id=locale_variant_id,
                decision=payload.decision,
                actor_id="founder",
                comment=payload.comment,
            )
    except ReviewActionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    except ReviewConsoleError as exc:
        status_code = 404 if exc.code.endswith("not_found") else 422
        raise HTTPException(status_code=status_code, detail=exc.code) from exc


@router.get("/content-cases/{content_case_id}/context", response_model=dict[str, Any])
async def get_journal_context(
    content_case_id: UUID,
    locale_variant_id: UUID = Query(...),  # noqa: B008
    knowledge_limit: int = Query(default=8, ge=1, le=8),  # noqa: B008
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    try:
        context = await build_journal_context(
            session,
            content_case_id=content_case_id,
            locale_variant_id=locale_variant_id,
            knowledge_limit=knowledge_limit,
        )
    except JournalContextError as exc:
        status_code = 404 if exc.code.endswith("not_found") else 422
        raise HTTPException(status_code=status_code, detail=exc.code) from exc
    return context.to_dict()