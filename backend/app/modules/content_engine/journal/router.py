from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.journal.context import (
    JournalContextError,
    build_journal_context,
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
    get_review_case,
    list_review_cases,
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


@router.get("/content-cases", response_model=list[JournalCaseResponse])
async def list_journal_cases(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[JournalCaseResponse]:
    rows = (
        await session.execute(
            select(ContentCase, ContentOpportunity, LocaleVariant)
            .join(
                ContentOpportunity,
                ContentOpportunity.id == ContentCase.content_opportunity_id,
            )
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


@router.get("/review-cases", response_model=list[ReviewCaseSummary])
async def list_journal_review_cases(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ReviewCaseSummary]:
    return await list_review_cases(session)


@router.get("/review-cases/{content_case_id}", response_model=ReviewCaseDetail)
async def get_journal_review_case(
    content_case_id: UUID,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReviewCaseDetail:
    try:
        return await get_review_case(session, content_case_id=content_case_id)
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


@router.get(
    "/content-cases/{content_case_id}/context",
    response_model=dict[str, Any],
)
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
