# F4 — Quality pipeline and final gate

Date: 2026-09-16
Status: IMPLEMENTATION CONTRACT
Base main: `5eef4e72cb15bc6ea30488a15f18a5de091053d6` (merged F3 / PR #104)

## Goal

Wire the existing Journal quality services into the canonical operator path:

`2 immutable Writer drafts -> bounded Review/Revise per locale -> Assertion Audit per locale -> deterministic Source-copy per locale -> exact final_content per locale -> WAIT_HUMAN(final_review)`

F4 stops at the third human gate. It MUST NOT persist a Founder final decision, ContentVersion, publish record, or F5 completion state.

## Reuse, do not rewrite

Reuse the existing:

- `ReviewReviseGenerator` and locale registry/agent bridge for `vi-VN` and `en`;
- durable Assertion Audit execution/recovery boundary and hard-gate `QualityEvaluation`;
- deterministic Source-copy v2 implementation and its exact findings/QE;
- harness `StepRun`, `Job`, leases, checkpoints, `pause_for_approval()`;
- Review Console read model and existing `submit_review_decision()` contract for the later F5 decision;
- canonical operator facade/resolver/state_version patterns from F1–F3.

No new evaluator framework, workflow engine, schema, provider, or client-side stage selector.

## Entry authority

F4 begins only when every persisted `JournalRequiredLocale` has exactly one completed F3 Writer lane with an immutable `journal_draft` bound to the exact approved Outline lineage.

The canonical resolver changes:

- `writers_to_quality`
- intent `continue`
- `executable=true`

Only after those exact F3 conditions hold.

One semantic Continue creates one parent `OperatorCommand` for the quality fan-out. The client never supplies locale, stage, provider, model, prompt, recipe or worker.

Replay of the same idempotency key reuses the command and creates no duplicate quality run/step/job/artifact.

## Per-locale quality lane

Each required locale remains independent. A completed sibling is never rolled back because the other locale fails.

Initial dispatch creates/reuses exactly one `Review/Revise` StepRun + durable Job per locale on the existing Writer run:

- `vi-VN -> review_revise_vi`
- `en -> review_revise_en`

The Writer run may transition from `waiting_approval` back to `running` using the existing harness transition contract.

The quality lane is anchored to the exact F3 source draft ID/version/hash. If newer draft bytes appear outside the expected stage transition, stale lineage fails closed.

### Stage 1 — bounded Review/Revise

Use `ReviewReviseGenerator` + the approved locale-specific agent bridge. No sibling draft or translation source is allowed as model input.

Successful output is a new immutable `journal_draft` on the same Writer run. Downstream quality stages bind this exact revised draft, not merely the newest draft by timestamp.

Model-output validation remains bounded by the existing generator policy. Durable Job retry is for technical execution failure only and is bounded to at most 2 Job attempts.

On success, enqueue/reuse the exact Assertion Audit stage for this locale.

### Stage 2 — Assertion Audit

Reuse the durable Assertion Audit run/handoff/StepRun/ContextManifest/ModelCall/QualityEvaluation contracts. The audit must bind the exact revised draft ID/version/hash and its Writer/Outline lineage.

Hard content failure is NOT an automatic retry:

- audit result `fail`, or
- critical unsupported count > 0, or
- critical contradicted count > 0

=> locale quality state is durably BLOCKED.

Execution/provider/lease failure may advertise a bounded retry only when the canonical retry limit permits it.

On pass/warn, enqueue/reuse the Source-copy stage for the same exact revised draft + exact audit artifact/evaluation.

### Stage 3 — Source-copy

Reuse Source-copy v2. It is deterministic and must not call a model or external provider.

Hard content failure:

- result `fail`, or
- fail_count > 0

=> locale quality state is durably BLOCKED and no final gate is prepared.

Warnings are acceptable and MUST survive verbatim in the operator/review read model. Do not auto-clean accepted warnings.

On pass/warn, the locale becomes quality-qualified.

## Aggregate progress and retry semantics

Canonical F4 progress must distinguish at least:

- not_dispatched
- review_queued / review_running
- audit_queued / audit_running
- source_copy_queued / source_copy_running
- qualified
- execution_failed_retryable
- execution_failed_exhausted
- quality_blocked
- final_gate_ready

The parent quality command remains queued while any child locale/stage is active.

When all active stages settle:

- all required locales qualified -> prepare final gate atomically;
- any retryable technical failure and no active sibling -> parent command failed, case BLOCKED + semantic retry;
- any exhausted technical failure -> parent command failed, fail closed, no retry advertised;
- any hard quality failure -> parent command failed with stable quality blocker, no automatic retry/revision advertised in F4.

Retry creates a new Job only for the exact failed technical stage/lane. It never recreates a completed sibling or reruns an already accepted prior stage.

Lease expiry/cancel settlement follows the F3 durable receipt rule: no OperatorCommand may remain queued forever after all child work is terminal.

## Final-gate preparation

Only when EVERY required locale is quality-qualified may F4 prepare the human final-review gate.

This preparation occurs in the same durable transaction that observes the last required Source-copy pass/warn (or an equivalent exact recovery path) so a crash cannot claim the gate without all persisted prerequisites.

For each required locale:

1. Ensure exactly one canonical `ContentItem` exists:
   - project = case project;
   - content_case = exact case;
   - locale_variant = exact required locale variant;
   - content_type = `journal`;
   - canonical key = `journal:{content_case_id}:{locale}`;
   - status remains non-published/draft-compatible.
   Conflicts fail closed. Do not create ContentVersion in F4.

2. Create/reuse exactly one `final_review` StepRun on the Writer run for the exact qualified draft lineage.

3. Create/reuse exactly one immutable `final_content` Artifact bound to that final-review StepRun.

4. `final_content.content_json` MUST be byte/JSON-equivalent to the exact quality-qualified `journal_draft.content_json`; its content hash MUST equal that source draft hash. F4 performs no additional rewriting/model call during final-content preparation.

5. Call canonical `pause_for_approval()` against the exact `final_review` StepRun + exact `final_content` artifact so the Writer run becomes `waiting_approval` with a checkpoint binding the artifact.

Gate preparation across required locales must be atomic from the case perspective: do not expose `WAIT_HUMAN(final_review)` while one required locale lacks its exact final artifact/checkpoint.

## Operator state and resolver

F4 state_version must cover durable state of every required locale quality lane, including at minimum:

- source/revised draft IDs/version/hash;
- Review/Revise StepRun and latest Job status/attempt;
- Assertion Audit run/step/job/artifact/evaluation/result;
- Source-copy run/step/job/artifact/evaluation/result and warning/fail counts;
- final_content ID/version/hash;
- final_review StepRun/checkpoint state.

Changing either locale or any quality artifact/evaluation must change aggregate state_version.

When all final gates are prepared:

- status = `AWAITING_APPROVAL`
- human_gate = `final_review`
- no automatic F5 action executes
- resolver returns the waiting action (`await_final_review_approval`), non-executable.

F4 must NOT create an Approval or ContentVersion.

## Read model

Extend the canonical operator view so F6 will not need DB knowledge. Expose one quality lane per required locale with at least:

- locale / locale_variant_id / writer_run_id;
- current quality stage + durable status;
- exact source/revised draft ref;
- Review/Revise step/job/attempt;
- Assertion Audit artifact/evaluation/result + critical/unsupported/contradicted counts;
- Source-copy artifact/evaluation/result + findings/warn_count/fail_count/max_overlap_tokens;
- final_content ref when prepared;
- final_review StepRun/checkpoint readiness;
- blocker code when any.

Existing Review Console semantics remain authoritative for final approval actions. F4 may reuse its representation but must not require the frontend to infer exact artifact bindings from DB state.

## Stale and partial-state rules

Fail closed on:

- multiple required variants or missing required locale;
- multiple candidate current source drafts for one lane;
- changed source draft after a quality stage was bound;
- mismatched audit/source-copy artifact/evaluation lineage;
- duplicate active stage runs/jobs that cannot be deterministically reconciled;
- conflicting ContentItem canonical identity;
- conflicting final_content/final_review gate state.

Completed sibling locale results remain immutable and reusable after a partial failure/retry.

Do not display an obsolete failed evaluation as the verdict for newer draft bytes.

## Implementation shape

Prefer a small Journal-owned operator module, e.g. `operator_quality.py`, plus a quality worker boundary, rather than extending `operator_runtime.py` into a monolith.

The existing persistent `run_operator_worker.py` may claim the allow-listed F4 jobs after Angle/Outline/Writer jobs using deterministic stage keys. It must not claim unrelated harness jobs.

No schema migration is expected. If implementation appears to require one, STOP for MG review before adding it.

## Required regression coverage

At minimum prove:

1. completed Writers -> `writers_to_quality / continue / executable=true`;
2. one Continue creates exactly 2 Review/Revise stages/jobs;
3. idempotency replay creates no duplicates;
4. VI and EN Review/Revise inputs never contain sibling drafts;
5. review success binds the exact revised draft into Assertion Audit;
6. audit hard fail blocks only that locale and does not enqueue Source-copy;
7. Source-copy fail blocks only that locale;
8. Source-copy warnings survive verbatim and still qualify;
9. technical failure/retry preserves completed sibling and accepted earlier stages;
10. retry exhaustion advertises no impossible retry;
11. lease expiry/cancel settles parent receipts;
12. stale source/revised/audit bindings fail closed;
13. after both locales qualify, ContentItems/final_content/final_review checkpoints are created exactly once;
14. each final_content hash equals its exact qualified journal_draft hash;
15. aggregate state_version changes when either locale/stage changes;
16. final state is `AWAITING_APPROVAL / final_review`;
17. Approval count created by F4 = 0;
18. ContentVersion count created by F4 = 0;
19. publish side effects = 0.

Implementation tests use fakes only. Real model/research execution requires a separate exact-head F4 acceptance authorization after MG review + green CI.

## F4 real acceptance exit

On a fresh exact-head synthetic bilingual case, prove:

`real Angle -> exact AngleApproval -> real Outline -> exact OutlineApproval -> real independent Writers -> one quality Continue -> real Review/Revise VI + EN -> real Assertion Audit VI + EN -> deterministic Source-copy VI + EN -> exact final_content VI + EN -> WAIT_HUMAN(final_review) -> STOP`

Allow PASS or WARN quality; warnings must be reported verbatim. Any hard quality fail stops acceptance without bypassing it.

Negative proof after STOP:

- Founder final Approval created by F4: 0
- ContentVersion created by F4: 0
- Publish: 0

## Out of scope

F4 does not implement:

- Founder approve / changes requested / reject execution;
- ContentVersion creation;
- case COMPLETE;
- publish/WordPress;
- automatic post-audit rewrite loops;
- generic evaluator platform;
- F6 UI redesign;
- tokenizer quality debt unrelated to a proven F4 blocker.

Those remain F5/F6 or later evidence-led work.