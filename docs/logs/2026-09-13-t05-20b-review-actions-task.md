# T05.20B — Vietnamese Review Console actions

## Goal

Add the smallest useful Founder decision surface to the persisted Journal Review Console after T05.20A passed end-to-end on the M1 runtime.

## Scope

- UI remains a content-production operator surface, not a repository-development task board.
- All operator-facing UI copy is Vietnamese.
- Add final-review actions per locale only: `Duyệt`, `Yêu cầu sửa`, `Từ chối`.
- Reuse the existing durable `final_review` Approval contract.
- `Duyệt` atomically persists the exact Founder approval, creates/reuses the locale ContentItem, creates one approved ContentVersion bound to exact final bytes, and completes the writer run.
- `Yêu cầu sửa` and `Từ chối` persist the exact durable decision only; they do not call a model or launch revision automatically.
- Allow browser POST only from the explicit local CORS allowlist already used by T05.20A.
- No publishing/WordPress action.

## Fail-closed rules

Actions are allowed only when all are true:

1. case/locale/final artifact bindings are exact and consistent;
2. current quality gate is PASS or accepted WARN with `fail_count = 0` and no critical assertion failures;
3. locale writer run is exactly `waiting_approval`;
4. latest checkpoint points to the exact `final_review` artifact;
5. no conflicting final decision exists;
6. no approved/published ContentVersion already exists for that exact finalization path.

Any stale, duplicate, conflicting, published, quality-blocked, or lineage-inconsistent state fails closed without partial writes.

## UX

- Vietnamese labels and explanations throughout the Review Console.
- Decision comment is required for `Yêu cầu sửa` and `Từ chối`; optional for `Duyệt`.
- Confirmation before a write action.
- Buttons are shown only when the locale is actually awaiting final Founder review.
- Existing M1 approved locale panels remain view-only and must not expose write buttons.
- Refresh persisted review state after a successful action.

## Explicit exclusions

- no publish button;
- no WordPress action;
- no model/provider/research/evaluator call;
- no automatic Review/Revise launch;
- no task-board/subagent UI in this slice;
- no migration unless an existing invariant proves impossible without one.

## Acceptance

- exact approve path creates one durable Approval + one approved ContentVersion and completes the run;
- changes-requested path creates one durable Approval, leaves no ContentVersion, and exposes revision-required state;
- rejected path creates one durable Approval, leaves no ContentVersion, and cancels the run;
- double submit/idempotent replay cannot create duplicate Approval or ContentVersion;
- stale artifact/checkpoint or quality failure cannot mutate state;
- M1 already-approved case remains unchanged and has no action buttons;
- all operator UI text is Vietnamese;
- CI full green.
