# CE05-T05.11-12-REAL-LOCAL-R1 — Repair missing vi-VN LocaleVariant and resume bilingual Writer gate

Owner: **Agent Local**
Status: **ACTIVE only after this task file is merged to main**

## Objective

Repair exactly one proven production-data blocker for the real O4 ContentCase:

`missing_vi_locale_variant`

Create/reuse exactly one `vi-VN` `LocaleVariant` with the approved bounded strategy below, without changing the existing `en` variant or any upstream content/research/runtime record. Then rerun the full real bilingual Writer gate from the beginning using the existing task:

`docs/logs/2026-09-10-ce05-real-o4-bilingual-writers-agent-local-task.md`

This explicit continuation is part of this assigned task. It is not permission to infer any further task after the bilingual Writer report.

## Locked blocker evidence

Agent Local already proved on clean main `b2c431d0e40b7935ed90bc0dfafc9a31798455f1`:

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
vi-VN LocaleVariant: 0 found
en LocaleVariant: exactly 1
  ID: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
  status: draft
  primary_question: How do I know if an original artwork is fairly priced?
  primary_intent: evaluate
Migration: 20260910_0018
Writer runs/handoffs/drafts/model calls: 0
```

No mutation occurred in the blocked run.

## Canonical strategy basis

The Founder-selected O4 opportunity already fixes:

```text
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
content type: journal
suggested role: cluster
intent: evaluate
preferred framing: How do I know if an original artwork is fairly priced?
```

Journal contract allows a distinct strategy per locale and forbids treating the other locale draft as the default translation source. The missing `vi-VN` record is therefore repaired as a locale-specific strategy record, not as a translated draft.

## Approved exact vi-VN LocaleVariant

Create/reuse exactly this record for ContentCase `9ec6133b-5f14-46d0-9866-e3b049e537b5`:

```text
locale: vi-VN
content_role: cluster
primary_question: Làm sao để biết giá của một tác phẩm nghệ thuật nguyên bản có hợp lý hay không?
primary_intent: evaluate
secondary_intent: null
primary_query: null
keyword_notes_json: []
emotion_arc_json: []
must_include_json: []
must_not_claim_json: []
status: draft
```

Rationale for nullable/empty fields: no Vietnamese-specific query, keyword, emotional-arc or claim-boundary evidence has been approved. Do not invent those fields merely to make the record look complete. Shared factual and brand boundaries remain enforced by the ContentCase, accepted Outline, EvidenceSet, OriginalityPack, SettingsSnapshot and Writer hard guards.

## Must read

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/03-DATA-CONTRACT.md`
6. `docs/08-JOURNAL-SPEC.md`
7. `docs/logs/2026-09-10-ce05-real-o4-bilingual-writers-agent-local-task.md`
8. this task

## Start-state preflight — read only

Fetch latest clean `main`, then verify before mutation:

- main contains this task file;
- working tree is clean;
- application DB migration is still exactly `20260910_0018` or `20260910_0019`;
- ContentCase `9ec6133b-5f14-46d0-9866-e3b049e537b5` exists exactly once and remains unchanged;
- existing `en` LocaleVariant exists exactly once with ID `19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc`;
- existing EN `content_role` is exactly `cluster`;
- existing EN `primary_intent` is exactly `evaluate`;
- `vi-VN` LocaleVariant count is either `0` or `1`;
- Writer localize runs = 0, writer handoffs = 0, journal drafts = 0, Writer ModelCalls = 0;
- source O4 run, accepted Outline and SettingsSnapshot remain exactly as locked in the original Writer task.

If EN role/intent differs, ContentCase/upstream differs, or VI count is greater than one: **BLOCKED / STOP**.

If VI count is exactly one, compare every approved field below. If every field matches exactly, treat repair as `reused=true` and do not mutate. If any field differs: **BLOCKED / STOP**; do not update an existing locale strategy in place.

## Exact bounded repair

Run from `backend/`. This is the only direct application-data mutation authorized by this repair stage.

```bash
python - <<'PY'
import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.content_engine.models import LocaleVariant

CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
EN_ID = UUID("19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc")

EXPECTED_VI = {
    "locale": "vi-VN",
    "content_role": "cluster",
    "primary_question": "Làm sao để biết giá của một tác phẩm nghệ thuật nguyên bản có hợp lý hay không?",
    "primary_intent": "evaluate",
    "secondary_intent": None,
    "primary_query": None,
    "keyword_notes_json": [],
    "emotion_arc_json": [],
    "must_include_json": [],
    "must_not_claim_json": [],
    "status": "draft",
}


def payload(row: LocaleVariant) -> dict[str, object]:
    return {
        "locale": row.locale,
        "content_role": row.content_role,
        "primary_question": row.primary_question,
        "primary_intent": row.primary_intent,
        "secondary_intent": row.secondary_intent,
        "primary_query": row.primary_query,
        "keyword_notes_json": row.keyword_notes_json,
        "emotion_arc_json": row.emotion_arc_json,
        "must_include_json": row.must_include_json,
        "must_not_claim_json": row.must_not_claim_json,
        "status": row.status,
    }


async def main() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            rows = list(
                (
                    await session.scalars(
                        select(LocaleVariant).where(LocaleVariant.content_case_id == CASE_ID)
                    )
                ).all()
            )
            en_rows = [row for row in rows if row.locale == "en"]
            vi_rows = [row for row in rows if row.locale == "vi-VN"]

            if len(en_rows) != 1 or en_rows[0].id != EN_ID:
                raise RuntimeError("blocked_en_locale_variant_identity_mismatch")
            if en_rows[0].content_role != "cluster":
                raise RuntimeError("blocked_en_content_role_mismatch")
            if en_rows[0].primary_intent != "evaluate":
                raise RuntimeError("blocked_en_primary_intent_mismatch")
            if len(vi_rows) > 1:
                raise RuntimeError("blocked_ambiguous_vi_locale_variant")

            reused = False
            if len(vi_rows) == 1:
                vi = vi_rows[0]
                if payload(vi) != EXPECTED_VI:
                    raise RuntimeError(
                        "blocked_existing_vi_locale_variant_differs_from_approved_contract"
                    )
                reused = True
            else:
                vi = LocaleVariant(content_case_id=CASE_ID, **EXPECTED_VI)
                session.add(vi)
                await session.flush()

            final_rows = list(
                (
                    await session.scalars(
                        select(LocaleVariant).where(LocaleVariant.content_case_id == CASE_ID)
                    )
                ).all()
            )
            final_vi = [row for row in final_rows if row.locale == "vi-VN"]
            final_en = [row for row in final_rows if row.locale == "en"]
            if len(final_vi) != 1 or len(final_en) != 1:
                raise RuntimeError("blocked_locale_variant_postcondition_failed")
            if payload(final_vi[0]) != EXPECTED_VI:
                raise RuntimeError("blocked_vi_locale_variant_postcondition_mismatch")

            result = {
                "repair": "vi-VN LocaleVariant",
                "reused": reused,
                "vi_locale_variant_id": str(final_vi[0].id),
                "en_locale_variant_id": str(final_en[0].id),
                "vi_payload": payload(final_vi[0]),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))


asyncio.run(main())
PY
```

The transaction must roll back automatically on any raised error.

## Repair acceptance gate

After the command, prove read-only:

```text
LocaleVariants for ContentCase: 1 -> 2
exact en count: 1 -> 1
exact vi-VN count: 0 -> 1
ContentRuns: unchanged
writer_handoff artifacts: unchanged
journal_draft artifacts: unchanged
Writer ModelCalls: unchanged
ToolCalls: unchanged
source O4 run: unchanged
Outline: unchanged
SettingsSnapshot: unchanged
EvidenceSet / OriginalityPack / AngleApproval: unchanged
```

Also report the new/reused VI LocaleVariant ID and every field in its payload.

No migration is required for the repair itself.

## Explicit resume authorization

If and only if the repair acceptance gate passes, **continue within this same assigned task** by executing the original Writer gate from its start:

`docs/logs/2026-09-10-ce05-real-o4-bilingual-writers-agent-local-task.md`

Re-run the original two-locale preflight. It must now find exactly one `vi-VN` and one `en` LocaleVariant before applying migration `20260910_0019` or executing either Writer.

Then execute all original Writer steps exactly, including:

```text
migration / registry verification
→ vi-VN first Writer execution
→ en first Writer execution
→ identical vi-VN rerun
→ identical en rerun
→ bilingual independence evidence
→ idempotency evidence
→ full VI draft
→ full EN draft
→ upstream immutability + scoped side-effect counts
```

All original Writer hard guards and stop conditions remain authoritative.

## Allowed actions

- fetch/pull clean current main;
- read application DB state;
- execute only the exact bounded `LocaleVariant` repair command above;
- if repair PASS, execute exactly the existing bilingual Writer task;
- apply migration `20260910_0019` only when reached by that existing Writer task;
- return evidence.

## Forbidden actions

- no repository edit/commit;
- no modification/deletion of the existing EN LocaleVariant;
- no update/delete of an existing VI LocaleVariant;
- no extra LocaleVariant;
- no query/keyword data invention;
- no ContentCase / Opportunity / NeedHypothesis mutation;
- no EvidenceSet / OriginalityPack / Angle / AngleApproval / Outline mutation;
- no source O4 run mutation;
- no prompt/recipe modification;
- no provider/model substitution;
- no research/Search/URL/ToolCall;
- no manual draft edit;
- no T05.13;
- no next-task inference;
- no merge.

## Output format

Return one combined report:

```text
TASK ID: CE05-T05.11-12-REAL-LOCAL-R1

START STATE

VI-VN LOCALE REPAIR PREFLIGHT

VI-VN LOCALE REPAIR RESULT
- inserted | reused
- vi LocaleVariant ID
- exact payload
- before/after locale counts
- non-target side-effect counts

WRITER GATE PREFLIGHT

MIGRATION / REGISTRY

LOCKED OUTLINE INPUT

RUNTIME ROUTE

VI-VN FIRST EXECUTION

VI-VN WRITER RUN / HANDOFF / PROVENANCE

FULL VI-VN DRAFT

EN FIRST EXECUTION

EN WRITER RUN / HANDOFF / PROVENANCE

FULL EN DRAFT

BILINGUAL INDEPENDENCE CHECK

IDEMPOTENCY / SECOND EXECUTIONS

UPSTREAM IMMUTABILITY

COUNTS / SIDE EFFECTS

TESTS / PROBES

RISKS / BLOCKERS

STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, **STOP**. Do not start T05.13.