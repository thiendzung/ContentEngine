from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.harness.outbox import ReconciliationResult, SideEffectRequest
from scripts import ops_rec02_proof as rec02


def test_rec02_source_has_no_polling_sleep_or_process_scan() -> None:
    source = Path(rec02.__file__).read_text(encoding="utf-8")

    assert "asyncio.sleep(" not in source
    assert "time.sleep(" not in source
    assert "pgrep" not in source
    assert '["ps"' not in source
    assert "_process_table" not in source
    assert "_wait_http(" not in source
    assert "call_later(" in source
    assert "process.communicate()" in source


def test_rec02_contract_uses_current_data02_revisions() -> None:
    assert rec02._SOURCE_REVISION == "20260915_0034"
    assert rec02._TARGET_REVISION == "20260926_0044"
    assert rec02._CRASH_EXIT_CODE != 0
    assert rec02._SHORT_LEASE_SECONDS > 0
    assert rec02._REPLACEMENT_LEASE_SECONDS > rec02._SHORT_LEASE_SECONDS


@pytest.mark.asyncio
async def test_fake_side_effect_reconciles_confirmed_success_without_resend() -> None:
    fake = rec02._FakeSideEffect()
    request = SideEffectRequest(
        intent_type="synthetic_rec02",
        idempotency_key="rec02:test:success",
        payload_ref="synthetic://payload-v1",
    )

    accepted = await fake.execute(request)
    reconciled = await fake.reconcile(request)

    assert fake.execute_count == 1
    assert reconciled == ReconciliationResult(
        outcome="confirmed_success",
        external_ref=accepted.external_ref,
    )


@pytest.mark.asyncio
async def test_fake_side_effect_reconciles_absent_without_execute() -> None:
    fake = rec02._FakeSideEffect()
    request = SideEffectRequest(
        intent_type="synthetic_rec02",
        idempotency_key="rec02:test:absent",
        payload_ref="synthetic://payload-v1",
    )

    reconciled = await fake.reconcile(request)

    assert fake.execute_count == 0
    assert reconciled == ReconciliationResult(outcome="confirmed_absent")


@pytest.mark.asyncio
async def test_fake_side_effect_reconciles_payload_conflict() -> None:
    fake = rec02._FakeSideEffect()
    original = SideEffectRequest(
        intent_type="synthetic_rec02",
        idempotency_key="rec02:test:conflict",
        payload_ref="synthetic://payload-v1",
    )
    changed = SideEffectRequest(
        intent_type="synthetic_rec02",
        idempotency_key=original.idempotency_key,
        payload_ref="synthetic://payload-v2",
    )

    accepted = await fake.execute(original)
    reconciled = await fake.reconcile(changed)

    assert fake.execute_count == 1
    assert reconciled.outcome == "conflict"
    assert reconciled.external_ref == accepted.external_ref


@pytest.mark.asyncio
async def test_callback_delay_uses_event_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[float] = []

    class _Handle:
        def cancel(self) -> None:
            return None

    class _Loop:
        def call_later(self, delay: float, callback: object) -> _Handle:
            called.append(delay)
            assert callable(callback)
            callback()
            return _Handle()

    monkeypatch.setattr(rec02.asyncio, "get_running_loop", lambda: _Loop())

    await rec02._callback_delay(0.25)

    assert called == [0.25]


def test_child_mode_does_not_require_backup_or_authorized_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rec02.sys,
        "argv",
        ["ops_rec02_proof.py", "--child-claim"],
    )

    args = rec02._parse_args()

    assert args.child_claim is True
    assert args.backup is None
    assert args.authorized_head is None
