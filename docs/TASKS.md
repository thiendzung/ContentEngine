# TASKS — ContentEngine V1

This file is the current roadmap and progress ledger. Detailed historical evidence belongs in `docs/logs/`.

Repository phase numbering here is authoritative for active work.

## Operating rule

Maximum active work:

```text
1 primary implementation task
+ 1 delegated local verification task
```

Local agents must synchronize their local repository to the exact GitHub ref before reading local task files or running local code. Do not activate the next task until the current semantic state is correct in the same PR where that transition is knowable.

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
- [x] T05.11 Draft writer `vi-VN` — implementation + real runtime/provenance/independence gate PASS.
- [x] T05.12 Draft writer `en` independently from Vietnamese — implementation + real runtime/provenance/independence gate PASS.

### Locked real O4 upstream lineage

```text
Source O4 ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
EvidenceSet hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
OriginalityPack hash: d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1
Angle artifact hash: e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
Selected Angle: angle-01
Candidate hash: 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872
Outline artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1
Outline hash: 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453
SettingsSnapshot hash: d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
```

### T05.11/T05.12 real Writer closeout

The missing `vi-VN` LocaleVariant was repaired through the bounded approved data task before either Writer ran.

Exact real Writer outputs:

```text
vi-VN LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
vi-VN Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
vi-VN draft v1: 19c2c580-efb6-43ba-b1a9-0625f0804ede
vi-VN draft hash: 972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6
vi-VN source unresolved count: 0

en LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
en Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
en draft v1: fdf54b59-92d3-4c42-ac14-e5a7ada26837
en draft hash: cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495
en source unresolved count: 5
```

Real runtime proved:

- [x] exactly one `vi-VN` and one `en` LocaleVariant;
- [x] two distinct `localize` ContentRuns, one per locale;
- [x] same accepted Outline, EvidenceSet, OriginalityPack and immutable SettingsSnapshot;
- [x] independent VI/EN prompt/recipe/task keys;
- [x] no sibling-draft or translation-source input;
- [x] exact section IDs/order and exact Evidence/Originality refs preserved;
- [x] no unsupported artwork/artist/commerce/market fact invented;
- [x] ToolCalls = 0;
- [x] exact reruns reuse the same Writer run/handoff/draft with zero extra ModelCalls;
- [x] source O4 run and all upstream artifacts remain immutable.

Contract correction:

`unresolved_factual_claims` is a deliberate safety handoff field. A Writer may enter T05.13 with declared gaps when it avoided writing the unsupported fact. Zero unresolved is therefore the **T05.13 exit gate**, not the T05.11/T05.12 entry gate.

Canonical decision:

`docs/logs/2026-09-10-ce05-writer-gate-contract-correction.md`

The five EN v1 items are accepted absence notes for T05.13. They do not require new research merely to enter revision.

### Current gate — T05.13 REAL BILINGUAL REVIEW / REVISE

Owner: **MG Content Engine** for implementation/contract/editorial review.

Post-merge Agent Local task:

`docs/logs/2026-09-10-ce05-real-o4-review-revise-agent-local-task.md`

T05.13 status:

- [ ] **T05.13 Review/revise bounded loop — implementation in current PR; real runtime/content gate pending.**

Implementation gate requires:

- [ ] exact immutable source draft v1 loaded by ID/version/hash;
- [ ] source draft lineage revalidated against same Writer run/handoff/Outline/EvidenceSet/OriginalityPack/SettingsSnapshot;
- [ ] same locale Writer run reused; no new ContentRun;
- [ ] locale-specific `review_revise_vi` / `review_revise_en` StepRun + ContextManifest + ModelCall;
- [ ] locale-specific active prompt/recipe registry through migration `20260910_0020`;
- [ ] same approved `codex_cli / gpt-5.6-luna` route reused from immutable SettingsSnapshot;
- [ ] no sibling draft input / no translation workflow;
- [ ] no research/Search/URL/ToolCall;
- [ ] exact Outline section IDs/order and support refs preserved;
- [ ] no new Evidence/Originality refs;
- [ ] declared gaps resolved only by removing/softening unsupported intended claims or using generic guidance that does not depend on missing facts;
- [ ] no missing artwork/artist/commerce/comparison/market fact invented;
- [ ] source v1 remains immutable;
- [ ] revised output persists as a new immutable `journal_draft` version;
- [ ] every document-level and section-level `unresolved_factual_claims` list is empty at T05.13 exit;
- [ ] exact rerun reuses revised artifact with zero extra ModelCall;
- [ ] focused tests + regression/lint/type/migration gates pass.

Real T05.13 gate additionally requires:

- [ ] migration `20260910_0020` applied and exact VI/EN review/revise registry verified;
- [ ] exact real VI v1 and EN v1 source snapshots verified unchanged;
- [ ] real VI review/revise produces one v2 in VI Writer run;
- [ ] real EN review/revise produces one v2 in EN Writer run;
- [ ] both revised drafts have zero unresolved factual claims;
- [ ] both Writer runs return to `waiting_approval`;
- [ ] support refs remain exactly equal to accepted Outline;
- [ ] both source v1 artifacts remain immutable;
- [ ] no upstream mutation and ToolCalls remain zero;
- [ ] exact repeated executions prove zero additional StepRun/ContextManifest/ModelCall/Artifact work;
- [ ] MG reviews both full revised drafts and marks T05.13 PASS.

### Critical path after T05.13 PASS

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
T05.13 implementation + CI
→ Founder merge
→ Agent Local synchronizes local main exactly to origin/main
→ migration 20260910_0020 + exact registry verification
→ real vi-VN review/revise from exact v1 → immutable v2
→ real en review/revise from exact v1 → immutable v2
→ zero unresolved + exact support refs
→ exact reruns prove v2 reuse / zero extra model calls
→ MG reviews both revised drafts
→ if PASS: T05.14 Assertion Audit
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

- [ ] link Angle/Outline/Writer/Review ModelCall `result_artifact_id` directly to persisted output artifacts or establish the equivalent canonical output-reference contract.

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
