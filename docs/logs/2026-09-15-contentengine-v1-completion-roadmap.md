# ContentEngine V1 Completion Roadmap

Date: 2026-09-15
Updated: 2026-09-16
Status: ACTIVE ROADMAP

Canonical detailed plan: `2026-09-16-finish-first-delivery-plan.md`.

## Definition of Done V1

ContentEngine V1 is ready for normal MOTGU Journal operation when Founder can use the browser to:

1. create a Journal from manual intake;
2. Start without selecting internal stage/provider/model;
3. reach and approve exact Angle;
4. continue to and approve exact Outline;
5. generate independent VI/EN content;
6. run bounded review/revise + assertion/source-copy checks;
7. reach final human review and persist canonical approved ContentVersions;
8. recover safely after refresh/restart/failure using durable state and idempotency;
9. operate on the local production stack with migration/recovery proven;
10. complete M1/M2/M3 before CE05 closeout.

Publishing/WordPress, Artwork Engine, broad CE06 expansion, vector DB, Antigravity production execution and native Codex multi-agent are not V1 blockers.

## Current repository truth

- `main = 77ad5fe329fbae577c6598f59ef63742fa782c3f`.
- K1-K6 and Model Routing Policy v1 are merged through PR #100.
- code migration chain reaches `20260915_0034`.
- operational DB remains at the last explicitly approved `20260914_0027` until guarded migration authorization.
- PR #93 UI-01 remains Draft on exact head `16d2d2ac101cb016566bc6d52ec923fab4560b97`; CI #1001 PASS.
- acceptance #2 is authorized and remains unconsumed until the new browser Job is actually claimed.

## Delivery principle

**Finish first, polish later.**

The repository already has the main domain/runtime engines. The shortest path is to connect them through one server-authoritative operator continuation flow, prove the whole browser path, then polish UI/UX from real operator evidence.

Do not build a generic workflow engine or redesign the whole frontend before the end-to-end path works.

## Feature completion lane

### F0 - Close UI-01 baseline

Exact browser proof through persisted AngleApproval, then Founder merge of PR #93. No Outline/Writer scope expansion.

### F1 - Unified operator core

Create one canonical operator-state projection and server-side next-action resolver. Frontend sends semantic intent only. Fail closed on ambiguity; preserve state-version/idempotency/Job semantics.

### F2 - Angle -> Outline

`AngleApproval -> durable Outline Job -> existing Outline path -> WAIT_HUMAN(outline) -> exact OutlineApproval`

### F3 - Outline -> independent VI/EN Writers

`OutlineApproval -> VI Writer + EN Writer`

Required locales are persisted truth. Each lane is durable and independently recoverable.

### F4 - Quality -> final gate

`Writer -> bounded Review/Revise -> Assertion Audit -> Source-copy -> WAIT_HUMAN(final_review)`

Persist pass/warn/fail and surviving warnings.

### F5 - Final -> COMPLETE

Exact final VI/EN review -> existing approve/request-changes/reject contracts -> canonical approved ContentVersions -> COMPLETE from required locales. No publish.

At this point Backend V1 is functionally complete for the normal Journal path.

### F6 - Minimum end-to-end operator UI

Keep only:

- `/production` for portfolio/queue/triage;
- `/operator/journal/[caseId]` for the continuous case workspace.

Add a minimal app shell (header/menu/status footer), dense Production Board using only canonical backend fields, and one workspace covering Intake -> Angle -> Outline -> VI/EN -> Quality -> Final.

### F7 - M2 + M3 pilot

Two additional distinct bilingual Journals through the browser. Capture repeated failure classes, retry/recovery, model calls, latency, edit burden and operator friction.

### F8 - Polish / CE05 closeout

Only after pilot evidence: targeted regressions, richer search/filter, accessibility/responsive polish, stronger recovery UX, metrics baseline, backup/restore + resume/replay proof and final documentation sync.

## Operationalization lane

Operational work remains separately permissioned and should be scheduled when required for the next real production proof.

### O1 - Operational migration `0027 -> 0034`

Fresh backup -> disposable restore -> freeze M1 -> guarded migration -> preflight -> prove M1 unchanged. Founder authorization required.

### O2 - Model Routing Policy activation

Create a new immutable approved SettingsVersion only after Founder chooses exact policy/provider/model allowlist and test proof passes. Do not mutate historical settings or infer production defaults.

Legacy routing may remain valid while feature completion proceeds if current contracts are sufficient.

## UI/UX model

The supplied dense task-board image is a visual reference only, not a data contract.

Production Board may use columns such as:

`ID | Content | Stage | Locale | Quality | Updated | Next action`

and groups:

`Running | Awaiting approval | Blocked | Ready | Completed`.

Do not invent `Due`, `Labels` or `Project` fields without canonical backend data.

The case workspace is the primary operating surface. Technical IDs, hashes, worker/provider/model telemetry remain secondary details.

## Collaboration model

GitHub is the shared brain.

- Founder: decisions, authorization, task relay, PR merge.
- MG / ChatGPT: architecture, code, review, plan, GitHub state and exact copy-paste local tasks.
- Agent Local: exact local execution/proof and evidence.

There is no assumed direct MG-to-Agent-Local communication. Founder copies MG tasks into Agent Local and returns Agent Local reports to MG for review before GitHub truth advances.

## Immediate order

`F0 -> F1 -> F2 -> F3 -> F4 -> F5 -> F6 -> O1/O2 when required -> F7 -> F8`
