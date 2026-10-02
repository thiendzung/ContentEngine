from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ops_local_e2e01 as local_e2e


def test_local_e2e_contract_is_disposable_and_current() -> None:
    assert local_e2e._SOURCE_REVISION == "20260915_0034"
    assert local_e2e._TARGET_REVISION == "20260926_0044"
    assert local_e2e._RUNTIME_DB_SUFFIX == "_local_e2e01_test"
    assert local_e2e._MAX_WORKER_TRANSITIONS > 0


def test_local_e2e_source_has_no_polling_sleep_or_process_scan() -> None:
    source = Path(local_e2e.__file__).read_text(encoding="utf-8")

    assert "asyncio.sleep(" not in source
    assert "time.sleep(" not in source
    assert "pgrep" not in source
    assert '["ps"' not in source
    assert "_wait_http(" not in source
    assert "process.communicate()" in source


def test_frozen_intake_is_bilingual_distinct_logistics_cluster() -> None:
    path = Path(__file__).resolve().parents[2] / "docs" / "LOCAL_E2E01_INTAKE.json"

    payload = local_e2e._load_intake(path)

    assert payload["content_role"] == "cluster"
    assert sorted(payload["required_locales"]) == ["en", "vi-VN"]
    assert "airline baggage" in str(payload["question"])
    assert "destination rules" in str(payload["question"])
    coverage = payload["coverage_requirements"]
    assert isinstance(coverage, list)
    assert len(coverage) == 6
    assert any("no universal carry-on" in str(item) for item in coverage)
    assert any("biosecurity" in str(item) for item in coverage)


@pytest.mark.asyncio
async def test_drive_stops_at_blocked_without_automatic_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked_view = {
        "state": {
            "status": "BLOCKED",
            "primary_intent": "retry",
            "phase": "start_to_angle",
        }
    }

    async def fake_view(_client: object, _case_id: str) -> dict[str, object]:
        return blocked_view

    async def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("blocked case must not auto retry")

    monkeypatch.setattr(local_e2e, "_view", fake_view)
    monkeypatch.setattr(local_e2e, "_submit_next", forbidden)
    monkeypatch.setattr(local_e2e, "_run_worker", forbidden)

    view, receipts = await local_e2e._drive_to_gate(
        object(),  # type: ignore[arg-type]
        "case-1",
        {"PATH": "/usr/bin"},
    )

    assert view is blocked_view
    assert receipts == []


@pytest.mark.asyncio
async def test_drive_is_event_chained_after_worker_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    views = iter(
        [
            {
                "state": {
                    "status": "READY",
                    "primary_intent": "continue",
                    "state_version": "a" * 64,
                    "phase": "outline",
                }
            },
            {
                "state": {
                    "status": "QUEUED",
                    "primary_intent": None,
                    "state_version": "b" * 64,
                    "phase": "outline",
                }
            },
            {
                "state": {
                    "status": "AWAITING_APPROVAL",
                    "human_gate": "outline",
                    "primary_intent": None,
                    "state_version": "c" * 64,
                    "phase": "outline",
                },
                "pending_gate": {"type": "outline"},
            },
        ]
    )
    calls: list[str] = []

    async def fake_view(_client: object, _case_id: str) -> dict[str, object]:
        return next(views)

    async def fake_submit(
        _client: object,
        _case_id: str,
        _state: dict[str, object],
    ) -> dict[str, object]:
        calls.append("submit")
        return {"status": "queued"}

    async def fake_worker(_env: dict[str, str]) -> dict[str, object]:
        calls.append("worker-exit")
        return {"status": "completed", "job_id": "job-1"}

    monkeypatch.setattr(local_e2e, "_view", fake_view)
    monkeypatch.setattr(local_e2e, "_submit_next", fake_submit)
    monkeypatch.setattr(local_e2e, "_run_worker", fake_worker)

    view, receipts = await local_e2e._drive_to_gate(
        object(),  # type: ignore[arg-type]
        "case-1",
        {"PATH": "/usr/bin"},
    )

    assert calls == ["submit", "worker-exit"]
    assert len(receipts) == 2
    assert view["state"]["human_gate"] == "outline"  # type: ignore[index]


def test_gate_requires_exact_human_gate() -> None:
    view = {
        "state": {
            "status": "AWAITING_APPROVAL",
            "human_gate": "angle",
        },
        "pending_gate": {"type": "angle", "artifact": {"id": "a"}},
    }

    assert local_e2e._gate(view, "angle")["type"] == "angle"

    with pytest.raises(local_e2e.LocalE2E01Error, match="local_e2e01_expected_gate_missing"):
        local_e2e._gate(view, "outline")


def test_parse_start_requires_explicit_state_and_intake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_e2e.sys,
        "argv",
        [
            "ops_local_e2e01.py",
            "start",
            "/tmp/backup.dump",
            "--intake",
            "/tmp/intake.json",
            "--authorized-head",
            "a" * 40,
            "--state-file",
            "/tmp/state.json",
        ],
    )

    args = local_e2e._parse_args()

    assert args.command == "start"
    assert args.intake == Path("/tmp/intake.json")
    assert args.state_file == Path("/tmp/state.json")
