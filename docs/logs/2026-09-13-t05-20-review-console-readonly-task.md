# T05.20A — Smallest useful Review Console (read-only first)

Owner: MG implementation; Agent Local local verification; Founder merge.

Status: PLANNED / NOT EXECUTED.

## Why this is next

M1 is complete on a real local bilingual Journal lineage. The main observed operator cost is not missing orchestration; it is fragmented review state across ContentCase, LocaleVariant, final draft/final_content artifacts, audits/QEs, Source-copy findings, Founder approval and ContentVersion identity.

The current frontend is a Journal Context workspace and the current Journal router exposes only ContentCase listing and per-locale context. The next useful surface is therefore a compact review console over existing persisted truth, not a dashboard, workflow designer or new engine.

## Goal

Add one read-only Review Console that lets an operator answer, without SQL or terminal archaeology:

- what Journal cases exist;
- which locale variants exist and where each is in the lifecycle;
- what the current visible VI/EN content is;
- which exact final artifacts / approved ContentVersions are bound;
- what Assertion Audit and Source-copy results/warnings survive;
- what Angle/Outline approval lineage applies;
- whether final Founder approval exists;
- what the next operational action is;
- whether anything is published.

This slice must be useful with the completed M1 case immediately.

## Explicit non-goals

Do NOT in T05.20A:

- mutate approvals;
- create ContentVersions;
- request revision/reject/approve through the UI;
- regenerate content;
- call models/providers/tools/research/evaluators;
- add a workflow engine/state machine;
- add dashboard analytics;
- add WordPress/publish actions;
- add a new DB schema/migration unless a demonstrated read-model blocker makes it unavoidable;
- parse local Operational Package files as runtime truth;
- special-case the M1 UUIDs in application code.

Approve / Request revision / Reject actions belong in T05.20B after the read model is proven against real state and can reuse the existing harness approval contract safely.

## Existing surfaces to reuse

Backend:

- `backend/app/modules/content_engine/journal/router.py`
- existing `ContentCase`, `LocaleVariant`, `ContentItem`, `ContentVersion`
- harness `Artifact`, `Approval`, `QualityEvaluation`, `ContentRun`, `StepRun`
- existing journal Angle/Outline approval records
- existing audit/source-copy artifact/QE payloads

Frontend:

- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`
- existing API base/generation pipeline under `frontend/src/lib/api/`

Do not introduce a second frontend shell.

## Backend slice

Add a read-only review representation under the existing `/journal` router.

Preferred endpoints:

1. `GET /journal/review-cases`
2. `GET /journal/review-cases/{content_case_id}`

If one endpoint shape is demonstrably simpler and bounded, MG may collapse them, but keep list payload small and detail payload complete.

### List response

Per ContentCase, expose only operator-summary fields needed for navigation:

- ContentCase ID/status/content_type;
- opportunity question/decision;
- available locales;
- per-locale ContentItem ID/canonical_key/status if present;
- current approved ContentVersion ID/version/status if present;
- current Writer run status if resolvable;
- final approval presence;
- aggregate quality state: `PASS | WARN | FAIL | PENDING`;
- publication state: `NOT_PUBLISHED | PUBLISHED` using persisted canonical data only;
- derived `next_action` string/code.

Do not include full draft text in list responses.

### Detail response

Return a bilingual/operator-centric representation, not raw table dumps.

At minimum:

- ContentCase core context: question, reader_before, reader_after, content_hypothesis;
- approved Angle artifact/selection/approval identifiers when present;
- approved Outline artifact/approval identifiers when present;
- one locale panel for each LocaleVariant;
- locale, ContentItem ID/canonical_key/status;
- current approved ContentVersion ID/version/status;
- exact final_content Artifact ID/version/hash;
- complete visible content fields: title, standfirst, lead, ordered sections with section_id/heading/body, closing;
- final Approval ID/actor/decision/comment when present;
- current Assertion Audit artifact/QE/result and critical counts when present;
- current Source-copy artifact/QE/result/fail_count/warn_count and every surviving warning/finding verbatim;
- provenance summary: Writer run, final draft source artifact if recoverable, final_content artifact, ContentVersion;
- publication state;
- derived `next_action`.

### Selection rules

The read model must fail closed and be deterministic.

- Never guess “latest” merely by timestamp when a stronger binding exists.
- Prefer `ContentVersion.final_artifact_id` for approved final content.
- Use exact ContentItem <-> LocaleVariant identity.
- Use the final artifact/run lineage to resolve the relevant approval and quality records; do not mix historical failed audits with current approved bytes.
- Preserve non-critical warnings verbatim.
- If bindings are ambiguous/conflicting, return an explicit `INCONSISTENT` state rather than choosing silently.
- Historical failed artifacts may be summarized as provenance later; T05.20A only needs the current approved state plus surviving warnings.

### Derived next_action baseline

Keep this a small pure function/read-model rule, not a new workflow engine.

Examples:

- approved ContentVersion + no publish record -> `APPROVED_NOT_PUBLISHED` / “Approved; publishing not authorized”;
- final artifact exists but no final approval -> `AWAITING_FOUNDER_APPROVAL`;
- hard quality failure for current bytes -> `QUALITY_BLOCKED`;
- no final artifact but Writer/review output exists -> `REVIEW_REQUIRED`;
- conflicting bindings -> `INCONSISTENT_STATE`;
- missing content -> `NOT_READY`.

Only implement states proven necessary by existing schema/current fixtures; avoid speculative lifecycle expansion.

## Frontend slice

Turn the existing single-page Journal workspace into a compact operator review surface without introducing a large design system.

Required layout:

### Left / navigation

- Journal case list;
- status/quality badge;
- obvious selected case;
- concise next-action text.

### Main

- VI and EN side-by-side on desktop; stacked on narrow screens;
- title/standfirst/lead/sections/closing rendered for reading, not as raw JSON;
- clear ContentVersion/status/final approval line per locale;
- warnings visible without opening developer tools;
- Assertion Audit and Source-copy status visible;
- “Not published” must be explicit for M1.

### Secondary/collapsible metadata

- approved Angle + approval;
- approved Outline + approval;
- artifact/version/hash IDs;
- Writer run / final_content / ContentVersion provenance;
- Source-copy warnings/findings verbatim.

### Utility

Add a client-side `Copy content` action per locale. It may copy the visible approved article as plain text/Markdown. It must have no server-side side effect.

Do not add active Approve/Reject/Request revision buttons in T05.20A. If placeholders are shown, they must be disabled and clearly labelled as not wired; omission is preferred.

## Tests

Backend focused tests must prove at least:

1. completed M1-style bilingual approved case returns both locales and correct current final binding;
2. approved ContentVersion resolves through `final_artifact_id` and does not accidentally surface an older failed audit artifact;
3. Source-copy warnings are returned verbatim;
4. no ContentItem/ContentVersion returns a bounded pending/not-ready state;
5. ambiguous/conflicting state fails closed as `INCONSISTENT_STATE`;
6. endpoints are read-only (row counts unchanged in test transaction).

Frontend verification:

- generated API types updated if OpenAPI changes;
- lint;
- typecheck;
- build;
- render path handles empty, error, pending and completed bilingual states without crashing.

No browser automation framework is required for this slice unless already available.

## Local verification on Founder runtime

After PR merge, Agent Local must:

- sync exact merged main, clean tree;
- keep operational DB intact;
- start/use existing backend/frontend only as documented;
- confirm M1 ContentCase appears;
- confirm both exact approved ContentVersions appear;
- confirm exact final hashes/IDs shown;
- confirm both EN warnings appear verbatim;
- confirm VI/EN visible copy is the approved final content;
- confirm UI says not published / publishing not authorized;
- confirm no DB row counts change merely by loading/using Review Console;
- confirm ModelCalls and ToolCalls unchanged;
- return screenshots only if they contain no secrets/private data.

## Acceptance

T05.20A passes when the Founder can open one local page and inspect the real M1 bilingual approved Journal state—including visible content, quality, warnings, approval/version provenance and next action—without terminal or SQL inspection, and doing so causes no runtime mutation.

Success status:

`STATUS: T05.20A READ-ONLY REVIEW CONSOLE PASS — READY FOR ACTION-WIRING DECISION`

Then STOP for MG review before T05.20B.