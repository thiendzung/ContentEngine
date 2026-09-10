# TASKS — ContentEngine V1

This file is the current roadmap and progress ledger. Detailed historical evidence belongs in `docs/logs/`.

Repository phase numbering here is authoritative for active work.

## Operating rule

Maximum active work:

```text
1 primary implementation task
+ 1 delegated local verification task
```

Do not activate the next task until the current semantic state is correct in the same PR where that transition is knowable. Runtime/human outcomes may require one intentional follow-up state transition after evidence exists.

---

## CE00 — Foundation Contracts

Status: **CLOSED / PASS**.

---

## CE01 — Repository Skeleton + Research Spike + Walking Skeleton

Status: **CLOSED / PASS**.

Key outcome: one real Golden Journal walking skeleton reached human review with zero critical unsupported assertions.

---

## CE02 — Core Data + Settings

Status: **CLOSED / PASS**.

T02.1–T02.23: **DONE**.

---

## CE03 — Durable Harness

Status: **CLOSED / PASS**.

T03.1–T03.20: **DONE**.

---

## CE04 — Knowledge + Production Research

Status: **CLOSED / PASS**.

T04.1–T04.35: **DONE**.

Canonical closeout evidence is retained in `docs/logs/`.

---

## CE05 — Journal Engine V1

Status: **ACTIVE**.

### Goal

Prove one real MOTGU Journal candidate end-to-end before adding more infrastructure.

### Completed foundation

- [x] T05.1 ContentCase/LocaleVariant Journal UI.
- [x] T05.2 Internal knowledge recall.
- [x] T05.3 Content Memory overlap check stub.
- [x] T05.4 Discovery Research step.
- [x] T05.5 Opportunity Map selection handoff.
- [x] T05.6 Evidence Research + EvidenceSet step.
- [x] T05.7 OriginalityPack step.
- [x] T05.8 Angle generator structured output implementation.
- [x] T05.9 Angle approval state/runtime bridge implementation.
- [x] T05.10 Outline with evidence mapping — implementation + one real O4 runtime + MG editorial gate PASS.
- [x] T05.11/T05.12 bilingual Writer implementation — independent locale runs, handoffs, prompts/recipes, idempotency guards and CI merged.

### Locked real O4 upstream lineage

```text
Source O4 ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1
Angle artifact hash: e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
Selected Angle: angle-01
Candidate hash: 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872
Outline artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1
Outline hash: 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453
```

T05.10 closeout:

`docs/logs/2026-09-10-ce05-real-o4-outline-closeout.md`

### Current gate — REAL BILINGUAL DRAFT GATE

Owner: **MG Content Engine** for blocker resolution and final editorial review.

Current delegated local execution after the blocker-handoff PR is merged:

`docs/logs/2026-09-10-ce05-real-o4-vi-locale-repair-and-resume-agent-local-task.md`

Original Writer runtime task remains canonical after the bounded repair:

`docs/logs/2026-09-10-ce05-real-o4-bilingual-writers-agent-local-task.md`

T05.11/T05.12 status:

- [ ] **T05.11 Draft writer `vi-VN` — implementation DONE / MERGED; real runtime blocked before execution because `vi-VN` LocaleVariant is missing.**
- [ ] **T05.12 Draft writer `en` independently from Vietnamese — implementation DONE / MERGED; real runtime intentionally not executed because the two-locale preflight is all-or-nothing.**

Implementation gate — **PASS / MERGED**:

- [x] both locale paths load the same exact accepted `journal_outline` Artifact;
- [x] each locale requires exactly one persisted LocaleVariant for the same ContentCase;
- [x] source O4 run remains upstream-only and unchanged;
- [x] each locale executes in its own `localize` ContentRun bound to its exact LocaleVariant and the same immutable SettingsSnapshot;
- [x] each locale Writer run has an immutable `writer_handoff` binding source O4 run + exact Outline + target LocaleVariant + SettingsSnapshot;
- [x] `vi-VN` and `en` use independent prompt/recipe definitions and locale-specific task keys;
- [x] neither Writer input contains or depends on sibling draft/run as writing input;
- [x] one immutable/versioned `journal_draft` Artifact per locale Writer run;
- [x] exact Outline/EvidenceSet/OriginalityPack/SettingsSnapshot/ContextManifest provenance;
- [x] locale-specific question/intent/must-include/must-not-claim data comes from the exact LocaleVariant;
- [x] lead and every section carry the exact support refs already assigned by the Outline;
- [x] no support-ref expansion or replacement inside Writer;
- [x] unsupported new factual claims are declared unresolved rather than invented;
- [x] no current artwork price/status/location, artist intent, scarcity or MOTGU pricing method is invented;
- [x] no research/tool calls;
- [x] bounded structured model output validation;
- [x] exact locale retry reuses the same Writer run/handoff/draft without another model call;
- [x] focused tests + regression/lint/type/migration gates pass.

Observed real-runtime blocker:

```text
First bilingual Writer preflight = BLOCKED / fail-closed
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
vi-VN LocaleVariant: 0
en LocaleVariant: exactly 1
  ID: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
  status: draft
  primary_question: How do I know if an original artwork is fairly priced?
  primary_intent: evaluate
Migration remained: 20260910_0018
Writer localize runs: 0
writer_handoff artifacts: 0
journal_draft artifacts: 0
Writer ModelCalls: 0
ToolCalls: 0
```

This is a bounded production-data completeness blocker. It did not expose a Writer implementation defect.

Repair contract:

- [ ] preflight confirms EN remains the exact existing record and matches canonical O4 `cluster/evaluate` strategy;
- [ ] create/reuse exactly one `vi-VN` LocaleVariant for the same ContentCase;
- [ ] VI exact strategy is `cluster` + `evaluate` with approved Vietnamese primary question;
- [ ] VI `primary_query`, secondary intent and locale-specific arrays remain null/empty because no VI-specific search/keyword evidence is approved;
- [ ] no EN/update/delete/upstream/migration/model/tool side effect during the repair itself;
- [ ] after repair, total LocaleVariants for the ContentCase move exactly `1 -> 2`;
- [ ] then re-run the full original bilingual Writer task from its start.

Real bilingual draft gate additionally requires:

- [ ] real ContentCase has exactly one `vi-VN` and exactly one `en` LocaleVariant; missing/ambiguous locale fails closed before either writer runs;
- [ ] migration `20260910_0019` applied and exact VI/EN registry verified;
- [ ] source O4 run and immutable SettingsSnapshot remain unchanged;
- [ ] both locale Writer runs use exactly `codex_cli / gpt-5.6-luna` via the already-approved `angle` route;
- [ ] real `vi-VN` localize Writer run creates one draft;
- [ ] real `en` localize Writer run independently creates one draft from the same Outline;
- [ ] both locale Writer runs return to `waiting_approval`;
- [ ] `unresolved_factual_claim_count = 0` for both drafts;
- [ ] exact repeated executions prove zero extra ContentRun/ModelCall/handoff/draft work;
- [ ] bilingual factual/support equivalence check passes;
- [ ] MG reviews both full drafts and marks the content gate PASS.

### Critical path after bilingual draft PASS

- [ ] T05.13 Review/revise bounded loop.
- [ ] T05.14 Assertion Audit.
- [ ] T05.15 Basic source-copy check.
- [ ] T05.16 Final content package.
- [ ] T05.17 One real MOTGU Journal end-to-end candidate.
- [ ] T05.18 Critical Gate Regression.
- [ ] T05.19 Resume / Replay Gate.
- [ ] T05.20 Human Review Surface.
- [ ] T05.21 CE05 Metrics Baseline.
- [ ] T05.22 CE05 Closeout.

### Immediate sequence

```text
bounded vi-VN LocaleVariant repair handoff PR
→ Founder merge
→ Agent Local executes repair + explicit resume task
→ exact vi-VN record exists and non-target side effects remain zero
→ original two-locale preflight passes
→ migration 20260910_0019 + registry check
→ real vi-VN + en localize Writer runs/drafts
→ exact locale reruns prove idempotency
→ MG reviews both drafts + independence
→ if PASS: T05.13 Review/Revise
→ T05.14 Assertion Audit
→ T05.15 source-copy check
→ T05.16 Final Package
→ T05.17 ONE REAL JOURNAL PASS
```

### Critical-path rule

Until T05.17 reaches one real Journal candidate:

- [ ] no new provider;
- [ ] no new agent role;
- [ ] no generic workflow builder;
- [ ] no architecture redesign;
- [ ] no speculative abstraction;
- [ ] no automated publishing;
- [ ] no automated merge;
- [ ] no CI optimization unless CI itself becomes a proven blocker.

Backlog after T05.17 unless proven blocking earlier:

- [ ] link Angle/Outline/Writer ModelCall `result_artifact_id` directly to persisted output artifacts or establish the equivalent canonical output-reference contract.

---

## CE06 — Full Quality + Golden Regression

Status: **NOT STARTED**.

- [ ] T06.1 Deterministic evidence/assertion evaluator.
- [ ] T06.2 Reader value evaluator.
- [ ] T06.3 Brand voice evaluator.
- [ ] T06.4 Reader transformation evaluator.
- [ ] T06.5 Originality evaluator.
- [ ] T06.6 Structure/readability evaluator.
- [ ] T06.7 Search/AI readability evaluator.
- [ ] T06.8 Language naturalness evaluator per locale.
- [ ] T06.9 Source-copy/phrase-overlap evaluator.
- [ ] T06.10 Human review form/UI.
- [ ] T06.11 Golden Set storage/versioning.
- [ ] T06.12 Weak/Failure Set storage.
- [ ] T06.13 Pairwise regression runner.
- [ ] T06.14 Candidate vs baseline report.
- [ ] T06.15 Regression promotion gate.

---

## CE07 — Artwork Engine V1

Status: **NOT STARTED**.

- [ ] T07.1 WordPress/WooCommerce canonical Artwork adapter.
- [ ] T07.2 Artwork fact lock.
- [ ] T07.3 MediaAsset ingest/ref mapping.
- [ ] T07.4 MediaObservation workflow + approval status.
- [ ] T07.5 Artist context retrieval.
- [ ] T07.6 Artist-intent provenance rule.
- [ ] T07.7 Artwork OriginalityPack.
- [ ] T07.8 Artwork writer `vi-VN`.
- [ ] T07.9 Artwork writer `en`.
- [ ] T07.10 Artwork Assertion Audit.
- [ ] T07.11 Related content linker.
- [ ] T07.12 Artwork quality gates.
- [ ] T07.13 One real MOTGU Artwork candidate.

---

## CE08 — WordPress Draft + Measurement Foundation

Status: **NOT STARTED**.

- [ ] T08.1 WordPress draft publish adapter.
- [ ] T08.2 ContentItem ↔ WordPress ID mapping.
- [ ] T08.3 ContentVersion PublishEvent history.
- [ ] T08.4 Idempotency/outbox/reconciliation.
- [ ] T08.5 Search Console adapter.
- [ ] T08.6 Analytics adapter.
- [ ] T08.7 MOTGU conversion-event mapping.
- [ ] T08.8 Normalize core PerformanceMetric values.
- [ ] T08.9 Preserve raw provider PerformanceSnapshot.
- [ ] T08.10 Rank Math signal feasibility spike.
- [ ] T08.11 Content hypothesis → metrics traceability.
- [ ] T08.12 Feed real Search Console queries back as Discovery/Keyword Plan signals, not automatic strategy changes.

---

## CE09 — Content Memory + Learning

Status: **NOT STARTED**.

- [ ] T09.1 Published ContentItem/Version memory index.
- [ ] T09.2 Duplicate/intent overlap detector.
- [ ] T09.3 Create/update/refresh/merge/do-not-write recommendation.
- [ ] T09.4 Human edit delta classifier.
- [ ] T09.5 Signal model/service.
- [ ] T09.6 LearningCandidate lifecycle.
- [ ] T09.7 Minimum-evidence/sufficiency rules.
- [ ] T09.8 Approved learning change workflow.
- [ ] T09.9 Regression-before-promotion enforcement.
- [ ] T09.10 Month 1 review report.
- [ ] T09.11 Month 3 review report.
- [ ] T09.12 Month 6 audience narrowing report.
- [ ] T09.13 Compare planned keyword/question map with real queries and update signal strength.

---

## CE10 — Pilot

Status: **NOT STARTED**.

- [ ] T10.1 Define 10–20 content hypotheses.
- [ ] T10.2 Balance pillar/cluster and Journal/Artwork.
- [ ] T10.3 Run production pilot.
- [ ] T10.4 Review quality failures.
- [ ] T10.5 Review human editing burden.
- [ ] T10.6 Review research provider cost/quality and remove redundant provider calls.
- [ ] T10.7 Review cost/latency overall.
- [ ] T10.8 Promote first stable Golden Set.
- [ ] T10.9 Review audience signals and evidence strength.
- [ ] T10.10 Decide next roadmap only from pilot evidence.
