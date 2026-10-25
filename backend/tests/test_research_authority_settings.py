from __future__ import annotations

from sqlalchemy import select
from test_ce05_review_revise import isolated_session

from app.modules.content_engine.models import Project, SettingsVersion
from app.modules.system.research_authority import (
    ResearchAuthoritySettingsError,
    configure_research_authority_hosts,
)
from app.modules.system.settings_service import resolve_settings_snapshot


async def _project(session):
    project = await session.scalar(
        select(Project).where(Project.slug == "motgu").limit(1)
    )
    assert project is not None
    return project


async def _active_project_settings(session, project_id):
    return await session.scalar(
        select(SettingsVersion)
        .where(
            SettingsVersion.project_id == project_id,
            SettingsVersion.scope_type == "project",
            SettingsVersion.scope_key == "motgu",
            SettingsVersion.status == "active",
        )
        .limit(1)
    )


async def _project_settings_rows(session, project_id):
    return list(
        (
            await session.scalars(
                select(SettingsVersion)
                .where(
                    SettingsVersion.project_id == project_id,
                    SettingsVersion.scope_type == "project",
                    SettingsVersion.scope_key == "motgu",
                )
                .order_by(SettingsVersion.version)
            )
        ).all()
    )


async def test_research_authority_settings_versions_and_replays() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        before = await _active_project_settings(session, project.id)
        before_json = dict(before.settings_json) if before is not None else {}

        result = await configure_research_authority_hosts(
            session,
            project_slug="motgu",
            trusted_evidence_hosts=[
                "smithsonianprovenance.si.edu",
                "www.getty.edu",
            ],
            approved_by="founder-test",
            change_reason="Test explicit evidence authority recovery.",
        )

        assert result.replayed is False
        assert result.trusted_evidence_hosts == (
            "smithsonianprovenance.si.edu",
            "www.getty.edu",
        )
        active = await _active_project_settings(session, project.id)
        assert active is not None
        assert active.id == result.settings_version_id
        assert active.approved_by == "founder-test"
        assert active.settings_json["research"] == {
            "trusted_evidence_hosts": [
                "smithsonianprovenance.si.edu",
                "www.getty.edu",
            ]
        }
        for key, value in before_json.items():
            if key != "research":
                assert active.settings_json[key] == value
        if before is not None:
            await session.refresh(before)
            assert before.status == "retired"

        rows_before_replay = await _project_settings_rows(session, project.id)
        replay = await configure_research_authority_hosts(
            session,
            project_slug="motgu",
            trusted_evidence_hosts=[
                "smithsonianprovenance.si.edu",
                "www.getty.edu",
            ],
            approved_by="founder-test",
            change_reason="Replay should not create a new version.",
        )
        rows_after_replay = await _project_settings_rows(session, project.id)

        assert replay.replayed is True
        assert replay.settings_version_id == result.settings_version_id
        assert len(rows_after_replay) == len(rows_before_replay)

        snapshot = await resolve_settings_snapshot(
            session,
            project_id=project.id,
            content_type="journal",
            locale="en",
        )
        research = snapshot.resolved_settings_json["research"]
        assert isinstance(research, dict)
        assert research["trusted_evidence_hosts"] == [
            "smithsonianprovenance.si.edu",
            "www.getty.edu",
        ]


async def test_research_authority_settings_reject_invalid_host_without_mutation() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        rows_before = await _project_settings_rows(session, project.id)

        try:
            await configure_research_authority_hosts(
                session,
                project_slug="motgu",
                trusted_evidence_hosts=["https://www.getty.edu/path"],
                approved_by="founder-test",
                change_reason="Invalid host must fail closed.",
            )
        except ResearchAuthoritySettingsError as exc:
            assert exc.code == "research_authority_host_invalid"
        else:
            raise AssertionError("invalid trusted evidence host was accepted")

        rows_after = await _project_settings_rows(session, project.id)
        assert [(row.id, row.status) for row in rows_after] == [
            (row.id, row.status) for row in rows_before
        ]
