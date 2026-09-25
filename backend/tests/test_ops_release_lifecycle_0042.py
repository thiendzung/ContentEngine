from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from scripts import ops_release_lifecycle as historical
from scripts import ops_release_lifecycle_0042 as lifecycle
from scripts.ops_release_provenance_0042 import ReleaseProvenanceError


class _NeverExitProcess:
    returncode = None
    pid = 12345

    async def wait(self) -> int:
        await asyncio.Event().wait()
        return 0


class _ExitedProcess:
    returncode = 1
    pid = 12345

    async def wait(self) -> int:
        return 1


def _runtime(
    *,
    process: object,
    ready: bool,
    tmp_path: Path,
) -> lifecycle.AsyncRuntime:
    event = asyncio.Event()
    if ready:
        event.set()

    async def completed_log_task() -> None:
        return None

    return lifecycle.AsyncRuntime(
        name="backend",
        process=process,  # type: ignore[arg-type]
        log_path=tmp_path / "backend.log",
        log_task=asyncio.create_task(completed_log_task()),
        ready_event=event,
    )


def test_historical_and_current_revision_contracts_are_distinct() -> None:
    assert historical._EXPECTED_REVISION == "20260915_0034"
    assert lifecycle._EXPECTED_REVISION == "20260923_0042"
    assert lifecycle._EXPECTED_DATABASE == "contentengine"



def test_current_snapshot_includes_publication_state() -> None:
    assert set(lifecycle._CURRENT_FINGERPRINT_TABLES) == {
        "jobs",
        "step_runs",
        "model_calls",
        "tool_calls",
        "outbox_intents",
        "published_contents",
        "publish_events",
    }

def _paused_retry_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "step_run_id": "step-1",
        "run_id": "run-1",
        "step_key": "start_to_angle",
        "step_status": "running",
        "step_error_class": "insufficient_evidence",
        "run_status": "running",
        "current_step": "start_to_angle",
        "run_failure_code": "insufficient_evidence",
        "job_id": "job-1",
        "job_run_id": "run-1",
        "job_status": "failed",
        "lease_owner": None,
        "lease_expires_at": None,
    }
    row.update(overrides)
    return row


def test_current_quiescence_accepts_exact_paused_operator_retry() -> None:
    paused = lifecycle._classify_paused_operator_retries(
        active_run_ids=["run-1"],
        active_steps=[_paused_retry_row()],
    )

    assert paused == [
        {
            "run_id": "run-1",
            "step_run_id": "step-1",
            "job_id": "job-1",
            "failure_class": "insufficient_evidence",
        }
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_status", "pending"),
        ("current_step", "outline"),
        ("step_key", "outline"),
        ("step_status", "pending"),
        ("job_id", None),
        ("job_run_id", "other-run"),
        ("job_status", "cancelled"),
        ("lease_owner", "worker-1"),
        ("lease_expires_at", "2026-09-25T00:00:00Z"),
        ("run_failure_code", ""),
        ("step_error_class", "different_failure"),
    ],
)
def test_current_quiescence_rejects_paused_contract_drift(
    field: str,
    value: object,
) -> None:
    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_quiescence_paused_contract_mismatch",
    ):
        lifecycle._classify_paused_operator_retries(
            active_run_ids=["run-1"],
            active_steps=[_paused_retry_row(**{field: value})],
        )


def test_current_quiescence_rejects_unmatched_active_run() -> None:
    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_quiescence_active_run_unmatched",
    ):
        lifecycle._classify_paused_operator_retries(
            active_run_ids=["run-1", "run-2"],
            active_steps=[_paused_retry_row()],
        )


def test_current_quiescence_rejects_unmatched_active_step() -> None:
    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_quiescence_active_step_unmatched",
    ):
        lifecycle._classify_paused_operator_retries(
            active_run_ids=[],
            active_steps=[_paused_retry_row()],
        )


def test_current_quiescence_rejects_multiple_active_steps_per_run() -> None:
    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_quiescence_multiple_active_steps",
    ):
        lifecycle._classify_paused_operator_retries(
            active_run_ids=["run-1"],
            active_steps=[
                _paused_retry_row(),
                _paused_retry_row(step_run_id="step-2", job_id="job-2"),
            ],
        )


@pytest.mark.asyncio
async def test_historical_idle_guard_still_blocks_running_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def statuses(_engine: object, *, table_name: str) -> dict[str, int]:
        values = {
            "jobs": {"failed": 1},
            "step_runs": {"running": 1},
            "content_runs": {"running": 1},
            "model_calls": {"completed": 1},
            "tool_calls": {"completed": 1},
            "outbox_intents": {},
        }
        return values[table_name]

    monkeypatch.setattr(historical, "_status_counts", statuses)

    with pytest.raises(
        historical.ReleaseLifecycleError,
        match="running_step_runs_present",
    ):
        await historical._assert_idle_operational_state(object())


@pytest.mark.asyncio
async def test_current_guard_accepts_paused_retry_and_returns_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def statuses(_engine: object, *, table_name: str) -> dict[str, int]:
        values = {
            "jobs": {"failed": 2},
            "step_runs": {"running": 2, "completed": 23, "failed": 1},
            "content_runs": {
                "running": 2,
                "completed": 9,
                "failed": 1,
                "waiting_approval": 4,
            },
            "model_calls": {"completed": 18},
            "tool_calls": {"completed": 15},
            "outbox_intents": {},
        }
        return values[table_name]

    async def active_rows(
        _engine: object,
    ) -> tuple[list[str], list[dict[str, object]]]:
        return (
            ["run-1", "run-2"],
            [
                _paused_retry_row(),
                _paused_retry_row(
                    run_id="run-2",
                    step_run_id="step-2",
                    job_id="job-2",
                    job_run_id="run-2",
                ),
            ],
        )

    monkeypatch.setattr(historical, "_status_counts", statuses)
    monkeypatch.setattr(lifecycle, "_active_release_rows", active_rows)

    evidence = await lifecycle._assert_release_quiescent_state(object())

    paused = evidence["paused_operator_retries"]
    assert isinstance(paused, list)
    assert [row["run_id"] for row in paused] == ["run-1", "run-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_name", "statuses", "blocker"),
    [
        ("jobs", {"queued": 1}, "nonterminal_jobs_present"),
        ("jobs", {"leased": 1}, "nonterminal_jobs_present"),
        ("model_calls", {"running": 1}, "active_model_calls_present"),
        ("tool_calls", {"pending": 1}, "active_tool_calls_present"),
        (
            "outbox_intents",
            {"needs_reconciliation": 1},
            "active_outbox_intents_present",
        ),
    ],
)
async def test_current_guard_blocks_live_work(
    monkeypatch: pytest.MonkeyPatch,
    table_name: str,
    statuses: dict[str, int],
    blocker: str,
) -> None:
    async def status_counts(_engine: object, *, table_name: str) -> dict[str, int]:
        defaults = {
            "jobs": {"failed": 1},
            "step_runs": {"running": 1},
            "content_runs": {"running": 1},
            "model_calls": {"completed": 1},
            "tool_calls": {"completed": 1},
            "outbox_intents": {},
        }
        if table_name == table_name_for_override:
            return statuses
        return defaults[table_name]

    async def active_rows(
        _engine: object,
    ) -> tuple[list[str], list[dict[str, object]]]:
        return ["run-1"], [_paused_retry_row()]

    table_name_for_override = table_name
    monkeypatch.setattr(historical, "_status_counts", status_counts)
    monkeypatch.setattr(lifecycle, "_active_release_rows", active_rows)

    with pytest.raises(lifecycle.ReleaseLifecycleError, match=blocker):
        await lifecycle._assert_release_quiescent_state(object())


def test_require_expected_revision_accepts_only_0042() -> None:
    lifecycle._require_expected_revision("20260923_0042")

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="operational_revision_not_current",
    ):
        lifecycle._require_expected_revision("20260915_0034")


def test_validate_release_inputs_binds_provenance_and_frontend_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    head = "a" * 40
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_checkout",
        lambda value: {"head": value, "clean": True},
    )
    monkeypatch.setattr(
        lifecycle,
        "validate_release_provenance",
        lambda **kwargs: {
            "git_head": head,
            "next_build_id": "build-0042",
            "package_lock_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_frontend_build",
        lambda: {
            "npm": "/usr/bin/npm",
            "build_id": "build-0042",
            "package_lock_sha256": "1" * 64,
        },
    )

    checkout, provenance, frontend = lifecycle._validate_release_inputs(
        authorized_head=head,
        provenance_path=tmp_path / "provenance.json",
    )

    assert checkout["head"] == head
    assert provenance["next_build_id"] == "build-0042"
    assert frontend["build_id"] == "build-0042"


def test_validate_release_inputs_rejects_provenance_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_checkout",
        lambda value: {"head": value, "clean": True},
    )

    def fail(**kwargs: object) -> dict[str, object]:
        raise ReleaseProvenanceError("release_provenance_mismatch")

    monkeypatch.setattr(lifecycle, "validate_release_provenance", fail)

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_provenance_mismatch",
    ):
        lifecycle._validate_release_inputs(
            authorized_head="a" * 40,
            provenance_path=tmp_path / "provenance.json",
        )


def test_validate_release_inputs_rejects_build_id_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_checkout",
        lambda value: {"head": value, "clean": True},
    )
    monkeypatch.setattr(
        lifecycle,
        "validate_release_provenance",
        lambda **kwargs: {
            "next_build_id": "old",
            "package_lock_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_frontend_build",
        lambda: {
            "npm": "/usr/bin/npm",
            "build_id": "new",
            "package_lock_sha256": "1" * 64,
        },
    )

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_build_id_mismatch",
    ):
        lifecycle._validate_release_inputs(
            authorized_head="a" * 40,
            provenance_path=tmp_path / "provenance.json",
        )


def test_validate_release_inputs_rejects_package_lock_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_checkout",
        lambda value: {"head": value, "clean": True},
    )
    monkeypatch.setattr(
        lifecycle,
        "validate_release_provenance",
        lambda **kwargs: {
            "next_build_id": "build",
            "package_lock_sha256": "1" * 64,
        },
    )
    monkeypatch.setattr(
        lifecycle.historical,
        "_validate_frontend_build",
        lambda: {
            "npm": "/usr/bin/npm",
            "build_id": "build",
            "package_lock_sha256": "2" * 64,
        },
    )

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_package_lock_mismatch",
    ):
        lifecycle._validate_release_inputs(
            authorized_head="a" * 40,
            provenance_path=tmp_path / "provenance.json",
        )


@pytest.mark.asyncio
async def test_await_ready_event_uses_event_and_not_http_polling(
    tmp_path: Path,
) -> None:
    runtime = _runtime(
        process=_NeverExitProcess(),
        ready=True,
        tmp_path=tmp_path,
    )

    await lifecycle._await_ready_event(
        runtime,
        timeout_seconds=0.1,
        code="ready_timeout",
    )


@pytest.mark.asyncio
async def test_await_ready_event_fails_when_process_exits_first(
    tmp_path: Path,
) -> None:
    runtime = _runtime(
        process=_ExitedProcess(),
        ready=False,
        tmp_path=tmp_path,
    )

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="backend_process_exited",
    ):
        await lifecycle._await_ready_event(
            runtime,
            timeout_seconds=0.1,
            code="ready_timeout",
        )


def test_current_lifecycle_source_has_no_sleep_or_http_retry_polling() -> None:
    source = Path(lifecycle.__file__).read_text(encoding="utf-8")

    assert "asyncio.sleep(" not in source
    assert "time.sleep(" not in source
    assert "_wait_http(" not in source
    assert "pgrep" not in source


def test_require_graceful_shutdown_rejects_forced_kill() -> None:
    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="forced_runtime_kill_restart",
    ):
        lifecycle._require_graceful_shutdown(
            [
                {
                    "name": "backend",
                    "exit_code": -9,
                    "forced_kill": True,
                    "log_path": "/tmp/backend.log",
                }
            ],
            cycle="restart",
        )


def test_require_graceful_shutdown_accepts_clean_exit() -> None:
    lifecycle._require_graceful_shutdown(
        [
            {
                "name": "backend",
                "exit_code": 0,
                "forced_kill": False,
                "log_path": "/tmp/backend.log",
            }
        ],
        cycle="startup",
    )


@pytest.mark.asyncio
async def test_current_preflight_wrapper_propagates_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blocked(*, blocker: str) -> dict[str, object]:
        raise lifecycle.ReleaseLifecycleError(
            blocker,
            evidence={"release_preflight": {"status": "BLOCKED"}},
        )

    monkeypatch.setattr(
        lifecycle.historical,
        "_require_release_preflight",
        blocked,
    )

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="pre_release_preflight_blocked",
    ) as exc_info:
        await lifecycle._require_release_preflight(
            blocker="pre_release_preflight_blocked"
        )

    assert exc_info.value.evidence == {
        "release_preflight": {"status": "BLOCKED"}
    }


@pytest.mark.asyncio
async def test_current_preflight_wrapper_returns_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ready(*, blocker: str) -> dict[str, object]:
        assert blocker == "post_release_preflight_blocked"
        return {"status": "READY", "checks": []}

    monkeypatch.setattr(
        lifecycle.historical,
        "_require_release_preflight",
        ready,
    )

    assert await lifecycle._require_release_preflight(
        blocker="post_release_preflight_blocked"
    ) == {"status": "READY", "checks": []}


@pytest.mark.asyncio
async def test_one_shot_http_readiness_makes_exactly_four_gets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Response:
        def __init__(self, url: str) -> None:
            self.url = url
            self.status_code = 200

        def json(self) -> dict[str, str]:
            if self.url.endswith("/version"):
                return {"version": "v1", "environment": "development"}
            return {"status": "ok"}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str) -> Response:
            calls.append(url)
            return Response(url)

    monkeypatch.setattr(
        lifecycle.httpx,
        "AsyncClient",
        lambda **kwargs: Client(),
    )

    result = await lifecycle._one_shot_http_readiness(
        settings_version="v1",
        settings_environment="development",
    )

    assert result["frontend"] == {"status": 200}
    assert calls == [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/health/db",
        "http://127.0.0.1:8000/version",
        "http://127.0.0.1:3000/",
    ]


def test_make_targets_use_current_generation_scripts() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )

    build_target = makefile.split("release-build-0042:", maxsplit=1)[1].split(
        "release-lifecycle-0042:", maxsplit=1
    )[0]
    lifecycle_target = makefile.split(
        "release-lifecycle-0042:",
        maxsplit=1,
    )[1].split("release-lifecycle:", maxsplit=1)[0]

    assert "ops_release_provenance_0042" in build_target
    assert "ops_release_lifecycle_0042" in lifecycle_target
    assert "ops_release_lifecycle --authorized-head" not in lifecycle_target
    assert 'test -n "$(AUTHORIZED_HEAD)"' in build_target
    assert 'test -n "$(AUTHORIZED_HEAD)"' in lifecycle_target
