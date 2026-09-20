"""Explicit Founder activation for the Journal promise-coverage registry v2."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import PromptDefinition, RecipeDefinition

JOURNAL_COVERAGE_REGISTRY_VERSION = 2
ANGLE_PROMPT_KEY = "journal_angle_candidates"
ANGLE_RECIPE_KEY = "journal_angle_v1"
OUTLINE_PROMPT_KEY = "journal_outline"
OUTLINE_RECIPE_KEY = "journal_outline_v1"

_PROMPT_KEYS = (ANGLE_PROMPT_KEY, OUTLINE_PROMPT_KEY)
_RECIPE_KEYS = (ANGLE_RECIPE_KEY, OUTLINE_RECIPE_KEY)


class JournalCoverageRegistryActivationError(RuntimeError):
    """Raised when registry v2 cannot be activated without guessing authority."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class JournalCoverageRegistryActivation:
    angle_prompt_id: UUID
    angle_recipe_id: UUID
    outline_prompt_id: UUID
    outline_recipe_id: UUID
    approved_by: str
    replayed: bool


def _required_text(value: str, code: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise JournalCoverageRegistryActivationError(code)
    return cleaned


async def _target_prompt(
    session: AsyncSession,
    *,
    key: str,
) -> PromptDefinition:
    row = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == key,
            PromptDefinition.version == JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
    )
    if row is None:
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_target_missing"
        )
    return row


async def _target_recipe(
    session: AsyncSession,
    *,
    key: str,
) -> RecipeDefinition:
    row = await session.scalar(
        select(RecipeDefinition).where(
            RecipeDefinition.recipe_key == key,
            RecipeDefinition.version == JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
    )
    if row is None:
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_target_missing"
        )
    return row


async def _active_prompts(
    session: AsyncSession,
) -> list[PromptDefinition]:
    return list(
        (
            await session.scalars(
                select(PromptDefinition)
                .where(
                    PromptDefinition.prompt_key.in_(_PROMPT_KEYS),
                    PromptDefinition.status == "active",
                )
                .order_by(PromptDefinition.prompt_key, PromptDefinition.version)
            )
        ).all()
    )


async def _active_recipes(
    session: AsyncSession,
) -> list[RecipeDefinition]:
    return list(
        (
            await session.scalars(
                select(RecipeDefinition)
                .where(
                    RecipeDefinition.recipe_key.in_(_RECIPE_KEYS),
                    RecipeDefinition.status == "active",
                )
                .order_by(RecipeDefinition.recipe_key, RecipeDefinition.version)
            )
        ).all()
    )


def _result(
    *,
    angle_prompt: PromptDefinition,
    angle_recipe: RecipeDefinition,
    outline_prompt: PromptDefinition,
    outline_recipe: RecipeDefinition,
    approved_by: str,
    replayed: bool,
) -> JournalCoverageRegistryActivation:
    return JournalCoverageRegistryActivation(
        angle_prompt_id=angle_prompt.id,
        angle_recipe_id=angle_recipe.id,
        outline_prompt_id=outline_prompt.id,
        outline_recipe_id=outline_recipe.id,
        approved_by=approved_by,
        replayed=replayed,
    )


async def activate_journal_promise_coverage_registry(
    session: AsyncSession,
    *,
    approved_by: str,
) -> JournalCoverageRegistryActivation:
    """Activate exact registry v2 only after an explicit approver is supplied.

    The caller owns the transaction. Old active v1 rows are retired first; if any
    later write fails, the caller must roll the transaction back.
    """

    approver = _required_text(
        approved_by,
        "journal_coverage_registry_approver_required",
    )
    angle_prompt = await _target_prompt(session, key=ANGLE_PROMPT_KEY)
    outline_prompt = await _target_prompt(session, key=OUTLINE_PROMPT_KEY)
    angle_recipe = await _target_recipe(session, key=ANGLE_RECIPE_KEY)
    outline_recipe = await _target_recipe(session, key=OUTLINE_RECIPE_KEY)
    targets: tuple[PromptDefinition | RecipeDefinition, ...] = (
        angle_prompt,
        outline_prompt,
        angle_recipe,
        outline_recipe,
    )

    active_targets = [row for row in targets if row.status == "active"]
    if len(active_targets) == len(targets):
        if any(row.approved_by != approver for row in targets):
            raise JournalCoverageRegistryActivationError(
                "journal_coverage_registry_active_approver_mismatch"
            )
        active_prompts = await _active_prompts(session)
        active_recipes = await _active_recipes(session)
        if {row.id for row in active_prompts} != {angle_prompt.id, outline_prompt.id}:
            raise JournalCoverageRegistryActivationError(
                "journal_coverage_registry_active_prompt_mismatch"
            )
        if {row.id for row in active_recipes} != {angle_recipe.id, outline_recipe.id}:
            raise JournalCoverageRegistryActivationError(
                "journal_coverage_registry_active_recipe_mismatch"
            )
        return _result(
            angle_prompt=angle_prompt,
            angle_recipe=angle_recipe,
            outline_prompt=outline_prompt,
            outline_recipe=outline_recipe,
            approved_by=approver,
            replayed=True,
        )

    if active_targets:
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_partial_activation"
        )
    if any(row.status != "draft" for row in targets):
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_target_state_invalid"
        )

    active_prompts = await _active_prompts(session)
    active_recipes = await _active_recipes(session)
    if any(
        row.version != 1 or row.prompt_key not in _PROMPT_KEYS
        for row in active_prompts
    ):
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_active_prompt_mismatch"
        )
    if any(
        row.version != 1 or row.recipe_key not in _RECIPE_KEYS
        for row in active_recipes
    ):
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_active_recipe_mismatch"
        )

    for row in (*active_prompts, *active_recipes):
        row.status = "retired"
    await session.flush()

    for row in targets:
        row.status = "active"
        row.approved_by = approver
    await session.flush()

    if {row.id for row in await _active_prompts(session)} != {
        angle_prompt.id,
        outline_prompt.id,
    }:
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_activation_failed"
        )
    if {row.id for row in await _active_recipes(session)} != {
        angle_recipe.id,
        outline_recipe.id,
    }:
        raise JournalCoverageRegistryActivationError(
            "journal_coverage_registry_activation_failed"
        )

    return _result(
        angle_prompt=angle_prompt,
        angle_recipe=angle_recipe,
        outline_prompt=outline_prompt,
        outline_recipe=outline_recipe,
        approved_by=approver,
        replayed=False,
    )


__all__ = [
    "JOURNAL_COVERAGE_REGISTRY_VERSION",
    "JournalCoverageRegistryActivation",
    "JournalCoverageRegistryActivationError",
    "activate_journal_promise_coverage_registry",
]
