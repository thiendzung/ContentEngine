"""Create the one durable Journal workflow run owned by operator case creation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase, ContentOpportunity, LocaleVariant
from app.modules.harness.models import ContentRun, utc_now
from app.modules.system.settings_service import SettingsResolutionError, resolve_settings_snapshot


class OperatorBootstrapError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def ensure_operator_bootstrap_run(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
) -> tuple[ContentRun, bool]:
    """Create/reuse the source-locale create run without inventing an executable stage."""
    content_case = await session.scalar(
        select(ContentCase)
        .where(ContentCase.id == content_case_id)
        .with_for_update()
    )
    if content_case is None or content_case.content_type != "journal":
        raise OperatorBootstrapError("operator_bootstrap_case_not_found")
    variant = await session.get(LocaleVariant, locale_variant_id)
    if variant is None or variant.content_case_id != content_case.id:
        raise OperatorBootstrapError("operator_bootstrap_locale_mismatch")

    existing = await session.scalar(
        select(ContentRun)
        .where(
            ContentRun.content_case_id == content_case.id,
            ContentRun.locale_variant_id == variant.id,
            ContentRun.run_mode == "create",
        )
        .order_by(ContentRun.created_at.asc(), ContentRun.id.asc())
        .limit(1)
    )
    if existing is not None:
        return existing, True

    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise OperatorBootstrapError("operator_bootstrap_opportunity_missing")
    try:
        snapshot = await resolve_settings_snapshot(
            session,
            project_id=opportunity.project_id,
            content_type="journal",
            locale=variant.locale,
        )
    except SettingsResolutionError as exc:
        raise OperatorBootstrapError(f"operator_bootstrap_{exc.code}") from exc

    run = ContentRun(
        project_id=opportunity.project_id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=None,
        run_mode="create",
        status="pending",
        current_step="intake",
        settings_snapshot_id=snapshot.id,
        started_at=utc_now(),
        completed_at=None,
        failure_code=None,
        failure_message=None,
    )
    session.add(run)
    await session.flush()
    return run, False


__all__ = ["OperatorBootstrapError", "ensure_operator_bootstrap_run"]
