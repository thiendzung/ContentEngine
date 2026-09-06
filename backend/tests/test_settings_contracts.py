from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project, SettingsSnapshot, SettingsVersion
from app.modules.system.settings_contracts import validate_brand_dna, validate_language_dna
from app.modules.system.settings_service import create_settings_snapshot


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_seed_project_and_independent_locale_settings_exist() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        versions = list(
            (
                await session.execute(
                    select(SettingsVersion).where(SettingsVersion.project_id == project.id)
                )
            ).scalars()
        )

    assert {version.scope_key for version in versions} >= {"motgu", "vi-VN", "en"}
    vi = next(version for version in versions if version.scope_key == "vi-VN")
    en = next(version for version in versions if version.scope_key == "en")
    assert vi.settings_json["language_dna"]["locale"] == "vi-VN"
    assert en.settings_json["language_dna"]["locale"] == "en"


def test_brand_and_language_dna_validate() -> None:
    validate_brand_dna(
        {
            "identity": {"category": "artist house", "positioning": "clear", "promise": "useful"},
            "voice": {
                "calm": "high",
                "intimate": "high",
                "poetic": "medium",
                "commercial": "low",
                "academic": "low",
            },
            "boundaries": {"avoid": ["fake scarcity"]},
            "proof_preferences": {"prefer": ["first-party facts"]},
        }
    )
    validate_language_dna(
        {
            "locale": "en",
            "audience_context": "reader",
            "vocabulary": {},
            "rhythm": {},
            "sensory_language": {},
            "rhetorical_questions": {},
            "metaphor": {},
            "direct_answer": {},
            "cta": {},
        }
    )


@pytest.mark.asyncio
async def test_snapshot_is_immutable_and_old_snapshot_survives_new_settings_version() -> None:
    async with isolated_session() as session:
        project = Project(slug=f"snapshot-{uuid4().hex[:8]}", name="MOTGU", default_locale="en")
        session.add(project)
        await session.flush()
        old_settings = {"brand": {"voice": "quiet"}}
        snapshot = await create_settings_snapshot(
            session,
            project_id=project.id,
            resolved_settings=old_settings,
            source_version_refs=["settings:1"],
        )
        session.add(
            SettingsVersion(
                project_id=project.id,
                scope_type="project",
                scope_key=project.slug,
                version=2,
                settings_json={"brand": {"voice": "warmer"}},
                status="active",
                change_reason="approved update",
            )
        )
        await session.flush()
        assert snapshot.resolved_settings_json == old_settings
        with pytest.raises(DBAPIError, match="settings_snapshots_are_immutable"):
            await session.execute(
                SettingsSnapshot.__table__.update()
                .where(SettingsSnapshot.id == snapshot.id)
                .values(resolved_settings_json={"changed": True})
            )
