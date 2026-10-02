from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_run02_min as run02


def test_run02_contract_is_current_and_disposable() -> None:
    assert run02._EXPECTED_SOURCE_REVISION == "20260915_0034"
    assert run02._EXPECTED_TARGET_REVISION == "20260926_0044"
    assert run02._BACKEND_HOST == "127.0.0.1"
    assert run02._BACKEND_PORT == 8000
    assert run02._FRONTEND_HOST == "127.0.0.1"
    assert run02._FRONTEND_PORT == 3000


def test_run02_source_has_no_polling_sleep_or_process_scan() -> None:
    source = Path(run02.__file__).read_text(encoding="utf-8")

    assert "asyncio.sleep(" not in source
    assert "time.sleep(" not in source
    assert "pgrep" not in source
    assert '["ps"' not in source
    assert "_process_table" not in source
    assert "_wait_http(" not in source


def test_runtime_env_targets_disposable_database() -> None:
    target = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/"
        "contentengine_run02_restore_test"
    )

    env = run02._runtime_env(target)

    assert env["APP_ENV"] == "development"
    assert env["DATABASE_URL"].endswith("/contentengine_run02_restore_test")
    assert env["NEXT_PUBLIC_API_BASE_URL"] == "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_worker_guard_accepts_terminal_jobs_and_empty_outbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def counts(_engine: object, *, table_name: str) -> dict[str, int]:
        if table_name == "jobs":
            return {"completed": 2, "failed": 7}
        if table_name == "outbox_intents":
            return {}
        raise AssertionError(table_name)

    monkeypatch.setattr(run02, "_status_counts", counts)

    evidence = await run02._require_one_shot_worker_idle(object())  # type: ignore[arg-type]

    assert evidence["jobs"] == {"completed": 2, "failed": 7}
    assert evidence["outbox_intents"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table_name", "statuses", "blocker"),
    [
        ("jobs", {"queued": 1}, "run02_claimable_job_present"),
        ("jobs", {"leased": 1}, "run02_claimable_job_present"),
        (
            "outbox_intents",
            {"needs_reconciliation": 1},
            "run02_active_outbox_present",
        ),
    ],
)
async def test_worker_guard_fails_closed_on_live_work(
    monkeypatch: pytest.MonkeyPatch,
    table_name: str,
    statuses: dict[str, int],
    blocker: str,
) -> None:
    async def counts(_engine: object, *, table_name: str) -> dict[str, int]:
        if table_name == target:
            return statuses
        return {}

    target = table_name
    monkeypatch.setattr(run02, "_status_counts", counts)

    with pytest.raises(run02.Run02Error, match=blocker):
        await run02._require_one_shot_worker_idle(object())  # type: ignore[arg-type]


def test_graceful_shutdown_accepts_non_forced_exit() -> None:
    run02._require_graceful_shutdown(
        [
            {
                "name": "backend",
                "exit_code": 0,
                "forced_kill": False,
                "log_path": "/tmp/backend.log",
            },
            {
                "name": "frontend",
                "exit_code": 0,
                "forced_kill": False,
                "log_path": "/tmp/frontend.log",
            },
        ],
        [],
    )


def test_graceful_shutdown_rejects_forced_kill() -> None:
    with pytest.raises(run02.Run02Error, match="runtime_forced_kill"):
        run02._require_graceful_shutdown(
            [
                {
                    "name": "backend",
                    "exit_code": -9,
                    "forced_kill": True,
                    "log_path": "/tmp/backend.log",
                }
            ],
            [],
        )


def test_graceful_shutdown_rejects_cleanup_error() -> None:
    with pytest.raises(run02.Run02Error, match="runtime_shutdown_failed"):
        run02._require_graceful_shutdown([], ["backend_shutdown_failed"])


class _IdleWorkerProcess:
    returncode = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return (
            b'{"status":"idle","worker_id":"operator:test:123"}\n',
            b"",
        )


class _UnexpectedWorkerProcess:
    returncode = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return (b'{"status":"completed","job_id":"unexpected"}\n', b"")


@pytest.mark.asyncio
async def test_one_shot_worker_requires_idle_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create(*args: object, **kwargs: object) -> _IdleWorkerProcess:
        assert "scripts.run_operator_worker" in args
        assert kwargs["cwd"] == str(run02._backend_root())
        return _IdleWorkerProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    result = await run02._run_one_shot_worker(env={"PATH": "/usr/bin"})

    assert result == {
        "status": "idle",
        "exit_code": 0,
        "worker_id": "operator:test:123",
    }


@pytest.mark.asyncio
async def test_one_shot_worker_rejects_any_job_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create(*args: object, **kwargs: object) -> _UnexpectedWorkerProcess:
        return _UnexpectedWorkerProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(run02.Run02Error, match="one_shot_worker_not_idle"):
        await run02._run_one_shot_worker(env={"PATH": "/usr/bin"})


@pytest.mark.asyncio
async def test_start_services_uses_event_driven_loopback_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_spawn(**kwargs: object) -> SimpleNamespace:
        calls.append(dict(kwargs))
        return SimpleNamespace(name=kwargs["name"])

    async def fake_stop(_runtimes: object) -> tuple[list[dict[str, object]], list[str]]:
        return [], []

    monkeypatch.setattr(run02.event_runtime, "_spawn_runtime", fake_spawn)
    monkeypatch.setattr(run02.event_runtime, "_stop_all", fake_stop)

    runtimes = await run02._start_services(
        env={"PATH": "/usr/bin"},
        npm="/usr/bin/npm",
        log_dir=tmp_path,
    )

    assert set(runtimes) == {"backend", "frontend"}
    backend = calls[0]["command"]
    frontend = calls[1]["command"]
    assert isinstance(backend, list)
    assert isinstance(frontend, list)
    assert ["--host", "127.0.0.1", "--port", "8000"] == backend[-5:-1]
    assert ["--hostname", "127.0.0.1", "--port", "3000"] == frontend[-4:]
