# F3 — OutlineApproval -> independent VI/EN Writers

Date: 2026-09-16
Status: ACTIVE IMPLEMENTATION CONTRACT
Base main: `0e789da83cd227e4b34b9c27657b554962b2d24d`

## Goal

Wire the already-proven bilingual Writer capability into canonical operator orchestration:

`OutlineApproval -> semantic Continue -> independent vi-VN/en Writer lanes -> immutable journal_draft artifacts -> STOP before Quality`

No Review/Revise, Assertion Audit, Source-copy, final approval, ContentVersion or publish work belongs in F3.

## Contract correction discovered at F3 start

Canonical Journal/Writer contracts use `vi-VN` and `en`, but the current manual operator intake still defaults/persists `vi` and `en`. F3 must remove this mismatch at the intake boundary rather than teaching the Writer to accept an inconsistent locale identifier.

Rules:

- canonical persisted required locales for newly created Journal cases: `vi-VN`, `en`;
- accept the legacy input alias `vi` only by normalizing it to `vi-VN` before persistence;
- source locale uses the same canonical value;
- frontend sends canonical `vi-VN`/`en` for new cases;
- do not mutate historical cases in place;
- F3 execution fails closed if a required locale cannot be mapped to one supported Writer locale or if the exact required LocaleVariant is missing/ambiguous.

## F3 orchestration design

1. An exact persisted `OutlineApproval` unlocks one backend-derived action: `outline_to_writers`.
2. UI sends only semantic `continue`; it never selects locale, stage, provider, model, prompt, recipe or worker.
3. Backend reads `JournalRequiredLocale` rows and creates/reuses exactly one locale-specific Writer run per required locale using existing `ensure_writer_run()`.
4. Each locale owns its own `ContentRun`, `StepRun`, `Job`, `ContextManifest`, `ModelCall` and immutable `journal_draft` artifact.
5. VI and EN consume the same exact approved Outline/evidence lineage but never consume a sibling locale draft.
6. Initial dispatch is atomic: partial lane creation must roll back.
7. Runtime execution is independent after dispatch: one locale may complete while another fails.
8. Retry is backend-derived and only requeues failed/cancelled required lanes; completed locale artifacts are never deleted or regenerated.
9. Aggregate operator/read-model progress lists every required locale explicitly.
10. F3 is complete only when every required locale has exactly one accepted Writer draft lineage. The next action is `writers_to_quality`, but it remains `executable=false` until F4.

## Required F3 proof

- fresh browser-operated case with canonical required locales `vi-VN` + `en`;
- exact OutlineApproval;
- one semantic Continue;
- exactly two Writer runs, two Writer StepRuns and two durable Jobs;
- separate real model calls for `writer_vi` and `writer_en`;
- both bind the same exact Outline id/version/hash and exact OutlineApproval;
- no sibling-draft/translation input;
- immutable `journal_draft` for each locale;
- idempotent replay creates no duplicate run/step/job/artifact;
- forced/fixture lane-failure test proves one locale's durable completion survives the other lane failure/retry;
- after both drafts, resolver returns `writers_to_quality`, `executable=false`;
- zero Review/Revise, Audit, Final, ContentVersion, publish execution.

## Stop condition

After both required Writer drafts exist and the canonical resolver reports `writers_to_quality / executable=false`, STOP and return evidence. F4 requires a new exact task.