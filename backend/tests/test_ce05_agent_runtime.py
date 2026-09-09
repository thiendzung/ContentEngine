from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.agent_bridge import (
    create_cli_angle_model_port,
)
from app.modules.content_engine.journal.angle import AngleGenerationError, AngleGenerator
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentRunnerError,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
    AntigravityCliRunner,
    CodexCliRunner,
)
from app.modules.harness.models import ContentRun, ModelCall
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import (
    SettingsResolutionError,
    resolve_settings_snapshot,
    settings_hash,
)


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


def _request(provider: str, model: str = "test-model") -> AgentRunRequest:
    return AgentRunRequest(
        provider=provider,
        model=model,
        prompt="Return the supplied JSON.",
        structured_output_schema={"type": "object"},
        working_context={"angle_model_input": {"evidence": [], "originality": []}},
        timeout=1.0,
    )


_CODEX_FEATURES = b"\n".join(
    f"{feature} stable true".encode()
    for feature in (
        "shell_tool",
        "unified_exec",
        "code_mode",
        "apps",
        "plugins",
        "enable_mcp_apps",
    )
)


def _codex_control_process(argv: tuple[str, ...]) -> FakeProcess | None:
    if argv[1:] == ("exec", "--help"):
        return FakeProcess(argv, stdout=b"--disable <FEATURE>")
    if argv[1:] == ("features", "list"):
        return FakeProcess(argv, stdout=_CODEX_FEATURES)
    return None


class FakeStdin:
    def __init__(self) -> None:
        self.data = b""
        self.closed = False

    def write(self, data: bytes) -> None:
        self.data += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class FakeProcess:
    def __init__(
        self,
        argv: tuple[str, ...],
        *,
        stdout: bytes = b"",
        exit_code: int = 0,
        last_message: object | None = None,
        hang: bool = False,
    ) -> None:
        self.argv = argv
        self.stdout = stdout
        self.returncode: int | None = None
        self._exit_code = exit_code
        self._last_message = last_message
        self._hang = hang
        self.killed = False
        self.stdin: FakeStdin | None = FakeStdin() if "exec" in argv or "headless" in argv else None
        if last_message is not None and "--output-last-message" in argv:
            target = Path(argv[argv.index("--output-last-message") + 1])
            target.write_text(json.dumps(last_message), encoding="utf-8")

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hang and not self.killed:
            await asyncio.Future()
        self.returncode = self._exit_code
        return self.stdout, b""

    def kill(self) -> None:
        self.killed = True


@pytest.mark.asyncio
async def test_codex_runner_uses_safe_argv_stdin_and_ignores_api_key_env(monkeypatch) -> None:
    processes: list[FakeProcess] = []

    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        control = _codex_control_process(argv)
        if control is not None:
            process = control
        elif argv[-2:] == ("login", "status"):
            process = FakeProcess(argv, stdout=b"Logged in using ChatGPT")
        elif "--version" in argv:
            process = FakeProcess(argv, stdout=b"codex 0.1-test")
        else:
            process = FakeProcess(
                argv,
                last_message={"candidates": [{"angle_id": "one"}]},
            )
        process.env = kwargs["env"]
        processes.append(process)
        return process

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-boundary")

    result = await CodexCliRunner().run(_request("codex_cli"))
    execution = processes[-1]
    assert result.structured_output == {"candidates": [{"angle_id": "one"}]}
    assert execution.stdin is not None and execution.stdin.closed
    assert "--model" in execution.argv
    assert "read-only" in execution.argv
    assert 'web_search="disabled"' in execution.argv
    assert execution.argv.count("--disable") == 6
    for feature in (
        "shell_tool",
        "unified_exec",
        "code_mode",
        "apps",
        "plugins",
        "enable_mcp_apps",
    ):
        assert ("--disable", feature) in zip(
            execution.argv,
            execution.argv[1:],
            strict=True,
        )
    assert "--search" not in execution.argv
    assert "OPENAI_API_KEY" not in execution.env
    assert "must-not-cross-boundary" not in execution.env.values()


@pytest.mark.asyncio
async def test_cli_runners_fail_closed_for_missing_or_unauthenticated_agent(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(AgentRunnerError, match="agent_executable_missing"):
        await CodexCliRunner().preflight()

    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        control = _codex_control_process(argv)
        if control is not None:
            return control
        if "--version" in argv:
            return FakeProcess(argv, stdout=b"codex 0.1-test")
        return FakeProcess(argv, stdout=b"Not logged in", exit_code=1)

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(AgentRunnerError, match="agent_auth_required"):
        await CodexCliRunner().preflight()


@pytest.mark.asyncio
async def test_antigravity_runner_uses_headless_json_schema_and_read_only(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        calls.append(argv)
        if "--version" in argv:
            return FakeProcess(argv, stdout=b"agy 1.0-test")
        if argv[-2:] == ("auth", "status"):
            return FakeProcess(argv, stdout=b"Google account authenticated")
        return FakeProcess(argv, stdout=b'{"candidates": []}')

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/agy")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await AntigravityCliRunner().run(_request("antigravity_cli"))
    execution = calls[-1]
    assert result.structured_output == {"candidates": []}
    assert execution[:2] == ("agy", "headless")
    assert "--output-format" in execution and "json" in execution
    assert "--json-schema" in execution
    assert "--sandbox" in execution and "read-only" in execution
    assert "--dangerously-skip-permissions" not in execution


@pytest.mark.asyncio
async def test_runner_timeout_is_fail_closed(monkeypatch) -> None:
    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        control = _codex_control_process(argv)
        if control is not None:
            return control
        if "--version" in argv:
            return FakeProcess(argv, stdout=b"codex 0.1-test")
        if argv[-2:] == ("login", "status"):
            return FakeProcess(argv, stdout=b"Logged in using ChatGPT")
        return FakeProcess(argv, hang=True)

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(AgentRunnerError, match="agent_timeout"):
        await CodexCliRunner().run(_request("codex_cli"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stdout", "exit_code", "error_code"),
    [
        (b"not-json", 0, "agent_output_invalid"),
        (b"{}", 3, "agent_nonzero_exit"),
    ],
)
async def test_cli_runner_rejects_invalid_or_nonzero_execution(
    monkeypatch,
    stdout: bytes,
    exit_code: int,
    error_code: str,
) -> None:
    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        control = _codex_control_process(argv)
        if control is not None:
            return control
        if "--version" in argv:
            return FakeProcess(argv, stdout=b"codex 0.1-test")
        if argv[-2:] == ("login", "status"):
            return FakeProcess(argv, stdout=b"Logged in using ChatGPT")
        return FakeProcess(argv, stdout=stdout, exit_code=exit_code)

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(AgentRunnerError, match=error_code):
        await CodexCliRunner().run(_request("codex_cli"))


@pytest.mark.asyncio
async def test_settings_resolver_precedence_and_exact_snapshot_retry() -> None:
    async with isolated_session() as session:
        from app.modules.content_engine.models import Project, SettingsVersion

        project = Project(slug=f"runtime-{uuid4().hex[:8]}", name="Runtime test")
        session.add(project)
        await session.flush()
        session.add_all(
            [
                SettingsVersion(
                    project_id=None,
                    scope_type="system",
                    scope_key="default",
                    version=1,
                    settings_json={"shared": {"base": True}, "models": {"draft": {"model": "sys"}}},
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
                SettingsVersion(
                    project_id=project.id,
                    scope_type="project",
                    scope_key=project.slug,
                    version=1,
                    settings_json={
                        "shared": {"project": True},
                        "models": {"draft": {"model": "sys"}},
                    },
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
                SettingsVersion(
                    project_id=project.id,
                    scope_type="content_type",
                    scope_key="journal",
                    version=1,
                    settings_json={"models": {"angle": {"route": "agent_angle"}}},
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
                SettingsVersion(
                    project_id=project.id,
                    scope_type="locale",
                    scope_key="en",
                    version=1,
                    settings_json={"language": {"locale": "en"}},
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
            ]
        )
        await session.flush()
        first = await resolve_settings_snapshot(
            session,
            project_id=project.id,
            content_type="journal",
            locale="en",
        )
        second = await resolve_settings_snapshot(
            session,
            project_id=project.id,
            content_type="journal",
            locale="en",
        )
        assert first.id == second.id
        assert first.resolved_settings_json["shared"] == {"base": True, "project": True}
        assert first.resolved_settings_json["models"]["angle"] == {"route": "agent_angle"}
        settings_rows = list(
            await session.scalars(
                select(SettingsVersion).where(
                    (SettingsVersion.project_id == project.id)
                    | SettingsVersion.project_id.is_(None)
                )
            )
        )
        scope_order = {"system": 0, "project": 1, "content_type": 2, "locale": 3}
        settings_rows.sort(key=lambda row: (scope_order[row.scope_type], row.scope_key))
        assert first.source_version_refs_json == [
            f"settings_version:{row.id}:v1"
            for row in settings_rows
        ]
        assert first.content_hash == settings_hash(first.resolved_settings_json)


@pytest.mark.asyncio
async def test_settings_conflicting_scope_values_fail_closed() -> None:
    async with isolated_session() as session:
        from app.modules.content_engine.models import Project, SettingsVersion

        project = Project(slug=f"runtime-{uuid4().hex[:8]}", name="Runtime test")
        session.add(project)
        await session.flush()
        session.add_all(
            [
                SettingsVersion(
                    project_id=None,
                    scope_type="system",
                    scope_key="default",
                    version=1,
                    settings_json={"models": {"angle": {"route": "system-A"}}},
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
                SettingsVersion(
                    project_id=project.id,
                    scope_type="project",
                    scope_key=project.slug,
                    version=1,
                    settings_json={"models": {"angle": {"route": "project-B"}}},
                    status="active",
                    change_reason="test",
                    approved_by="founder",
                ),
            ]
        )
        await session.flush()
        with pytest.raises(
            SettingsResolutionError,
            match="settings_override_policy_missing",
        ):
            await resolve_settings_snapshot(
                session,
                project_id=project.id,
                content_type="journal",
                locale="en",
            )


@pytest.mark.asyncio
async def test_run_override_conflict_and_draft_registry_fail_closed() -> None:
    async with isolated_session() as session:
        from app.modules.content_engine.models import Project, SettingsVersion

        project = Project(slug=f"runtime-{uuid4().hex[:8]}", name="Runtime test")
        session.add(project)
        await session.flush()
        session.add(
            SettingsVersion(
                project_id=project.id,
                scope_type="project",
                scope_key=project.slug,
                version=1,
                settings_json={"models": {"angle": {"route": "one"}}},
                status="active",
                change_reason="test",
                approved_by="founder",
            )
        )
        await session.flush()
        with pytest.raises(SettingsResolutionError, match="settings_override_policy_missing"):
            await resolve_settings_snapshot(
                session,
                project_id=project.id,
                content_type="journal",
                locale="en",
                run_override={"models": {"angle": {"route": "two"}}},
            )


@pytest.mark.asyncio
async def test_active_settings_version_is_unique_and_payload_immutable() -> None:
    async with isolated_session() as session:
        from app.modules.content_engine.models import Project, SettingsVersion

        project = Project(slug=f"runtime-{uuid4().hex[:8]}", name="Runtime test")
        session.add(project)
        await session.flush()
        settings = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=1,
            settings_json={"models": {"angle": {"route": "one"}}},
            status="active",
            change_reason="test",
            approved_by="founder",
        )
        session.add(settings)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                session.add(
                    SettingsVersion(
                        project_id=project.id,
                        scope_type="project",
                        scope_key=project.slug,
                        version=2,
                        settings_json={"models": {"angle": {"route": "two"}}},
                        status="active",
                        change_reason="test",
                        approved_by="founder",
                    )
                )
                await session.flush()
        with pytest.raises(DBAPIError, match="settings_versions_active_is_immutable"):
            async with session.begin_nested():
                settings.settings_json = {"models": {"angle": {"route": "changed"}}}
                await session.flush()


@pytest.mark.asyncio
async def test_active_prompt_and_recipe_payloads_are_immutable() -> None:
    async with isolated_session() as session:
        prompt = PromptDefinition(
            prompt_key=f"runtime_prompt_{uuid4().hex[:8]}",
            version=1,
            purpose="test",
            body="grounded",
            input_contract_json={"required": ["input"]},
            output_schema_json={"type": "object"},
            status="active",
            change_reason="test",
            approved_by="founder",
        )
        recipe = RecipeDefinition(
            recipe_key=f"runtime_recipe_{uuid4().hex[:8]}",
            version=1,
            selector_json={"content_type": "journal", "task": "angle"},
            recipe_json={"grounded": True},
            status="active",
            approved_by="founder",
        )
        session.add_all([prompt, recipe])
        await session.flush()
        with pytest.raises(DBAPIError, match="prompt_definitions_active_is_immutable"):
            async with session.begin_nested():
                prompt.body = "changed"
                await session.flush()
        with pytest.raises(DBAPIError, match="recipe_definitions_active_is_immutable"):
            async with session.begin_nested():
                recipe.recipe_json = {"grounded": False}
                await session.flush()


@pytest.mark.asyncio
async def test_activation_requires_non_empty_human_approval_for_all_registries() -> None:
    async with isolated_session() as session:
        from app.modules.content_engine.models import Project, SettingsVersion

        project = Project(slug=f"runtime-{uuid4().hex[:8]}", name="Runtime test")
        session.add(project)
        await session.flush()

        invalid_rows = [
            (
                SettingsVersion(
                    project_id=project.id,
                    scope_type="project",
                    scope_key=project.slug,
                    version=1,
                    settings_json={"test": "settings"},
                    status="active",
                    change_reason="test",
                ),
                "settings_versions_active_requires_approval",
            ),
            (
                SettingsVersion(
                    project_id=project.id,
                    scope_type="project",
                    scope_key=project.slug,
                    version=1,
                    settings_json={"test": "settings"},
                    status="active",
                    change_reason="test",
                    approved_by="",
                ),
                "settings_versions_active_requires_approval",
            ),
            (
                PromptDefinition(
                    prompt_key=f"runtime_prompt_{uuid4().hex[:8]}",
                    version=1,
                    purpose="test",
                    body="grounded",
                    input_contract_json={"required": ["input"]},
                    output_schema_json={"type": "object"},
                    status="active",
                    change_reason="test",
                ),
                "prompt_definitions_active_requires_approval",
            ),
            (
                PromptDefinition(
                    prompt_key=f"runtime_prompt_{uuid4().hex[:8]}",
                    version=1,
                    purpose="test",
                    body="grounded",
                    input_contract_json={"required": ["input"]},
                    output_schema_json={"type": "object"},
                    status="active",
                    change_reason="test",
                    approved_by="",
                ),
                "prompt_definitions_active_requires_approval",
            ),
            (
                RecipeDefinition(
                    recipe_key=f"runtime_recipe_{uuid4().hex[:8]}",
                    version=1,
                    selector_json={"content_type": "journal", "task": "angle"},
                    recipe_json={"grounded": True},
                    status="active",
                ),
                "recipe_definitions_active_requires_approval",
            ),
            (
                RecipeDefinition(
                    recipe_key=f"runtime_recipe_{uuid4().hex[:8]}",
                    version=1,
                    selector_json={"content_type": "journal", "task": "angle"},
                    recipe_json={"grounded": True},
                    status="active",
                    approved_by="",
                ),
                "recipe_definitions_active_requires_approval",
            ),
        ]
        for row, error_code in invalid_rows:
            with pytest.raises(DBAPIError, match=error_code):
                async with session.begin_nested():
                    session.add(row)
                    await session.flush()

        settings = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=1,
            settings_json={"test": "settings"},
            status="draft",
            change_reason="test",
        )
        prompt = PromptDefinition(
            prompt_key=f"runtime_prompt_{uuid4().hex[:8]}",
            version=1,
            purpose="test",
            body="grounded",
            input_contract_json={"required": ["input"]},
            output_schema_json={"type": "object"},
            status="draft",
            change_reason="test",
        )
        recipe = RecipeDefinition(
            recipe_key=f"runtime_recipe_{uuid4().hex[:8]}",
            version=1,
            selector_json={"content_type": "journal", "task": "angle"},
            recipe_json={"grounded": True},
            status="draft",
        )
        session.add_all([settings, prompt, recipe])
        await session.flush()
        settings.status = "active"
        settings.approved_by = "founder"
        prompt.status = "active"
        prompt.approved_by = "founder"
        recipe.status = "active"
        recipe.approved_by = "founder"
        await session.flush()


class FakeAngleRunner:
    def __init__(self, output: object) -> None:
        self.output = output
        self.requests: list[AgentRunRequest] = []

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fake-agent-1",
            structured_output=self.output,
            raw_output_hash="a" * 64,
            exit_code=0,
            usage={"input_tokens": 10, "output_tokens": 20},
            duration_ms=7,
            session_id="safe-session",
        )


@pytest.mark.asyncio
async def test_cli_angle_bridge_records_modelcall_and_passes_only_sanitized_input() -> None:
    from test_ce05_angle_approval import _bundle_fixture, _candidate_payload

    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        run = await session.get(ContentRun, bundle_artifact.run_id)
        assert run is not None
        snapshot = SettingsSnapshot(
            project_id=run.project_id,
            resolved_settings_json={
                "models": {"angle": {"route": "agent_angle"}},
                "model_routes": {"agent_angle": {"provider": "codex_cli", "model": "test-model"}},
            },
            source_version_refs_json=["runtime-test"],
            content_hash=settings_hash({"runtime": "test"}),
        )
        prompt = await session.scalar(
            select(PromptDefinition).where(
                PromptDefinition.prompt_key == "journal_angle_candidates"
            )
        )
        recipe = await session.scalar(
            select(RecipeDefinition).where(RecipeDefinition.recipe_key == "journal_angle_v1")
        )
        assert prompt is not None and recipe is not None
        prompt.status = "active"
        prompt.approved_by = "founder"
        recipe.status = "active"
        recipe.approved_by = "founder"
        session.add(snapshot)
        await session.flush()
        run.settings_snapshot_id = snapshot.id
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=None,
            inputs=ContextInputs(
                prompt_version="journal_angle_candidates:v1",
                recipe_version="journal_angle_v1:v1",
                evidence_set_id=bundle.evidence_set_id,
                originality_pack_id=bundle.originality_pack_id,
            ),
        )
        fake = FakeAngleRunner(
            {"candidates": [_candidate_payload(bundle, index) for index in range(1, 4)]}
        )
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_angle_model_port(
            session,
            run_id=run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
        )
        result = await AngleGenerator(max_attempts=1).generate_candidates(
            session,
            journal_input_bundle_id=bundle_artifact.id,
            model=port,
            provider="codex_cli",
            model_name="test-model",
        )
        request = fake.requests[0]
        serialized = json.dumps(request.working_context, sort_keys=True)
        assert "raw_provider_payload" not in serialized
        assert "search_snippets" not in serialized
        assert request.working_context["angle_model_input"] == bundle.angle_model_input
        call = await session.scalar(select(ModelCall).where(ModelCall.run_id == run.id))
        assert call is not None
        assert call.provider == "codex_cli"
        assert call.model == "test-model"
        assert call.status == "completed"
        assert call.runtime_metadata_json == {
            "runner_version": "fake-agent-1",
            "exit_code": 0,
            "raw_output_hash": "a" * 64,
            "duration_ms": 7,
            "session_id": "safe-session",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        assert len(result.candidates) == 3
        assert result.artifact.content_json["model"] == {
            "provider": "codex_cli",
            "model": "test-model",
        }

        before_requests = len(fake.requests)
        with pytest.raises(AngleGenerationError, match="angle_model_route_mismatch"):
            await AngleGenerator(max_attempts=1).generate_candidates(
                session,
                journal_input_bundle_id=bundle_artifact.id,
                model=port,
                provider="antigravity_cli",
                model_name="model-B",
            )
        assert len(fake.requests) == before_requests
