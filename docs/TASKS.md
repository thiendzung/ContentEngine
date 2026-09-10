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

Foundation contracts, canonical docs and governance established.

---

## CE01 — Repository Skeleton + Research Spike + Walking Skeleton

Status: **CLOSED / PASS**.

Key outcome: one real Golden Journal walking skeleton reached human review with zero critical unsupported assertions.

---

## CE02 — Core Data + Settings

Status: **CLOSED / PASS**.

T02.1–T02.23: **DONE**.

Key outcome: persisted core data, settings snapshots, prompt/recipe registry, content identity, evidence/originality, run/artifact/approval and model/tool telemetry contracts.

---

## CE03 — Durable Harness

Status: **CLOSED / PASS**.

T03.1–T03.20: **DONE**.

Key outcome: durable run/step/job state, lease/reclaim, checkpoint, approval pause/resume, bounded retry, budget, ModelRouter/ToolAdapter, ContextManifest, telemetry, outbox/reconciliation and replay/eval.

---

## CE04 — Knowledge + Production Research

Status: **CLOSED / PASS**.

T04.1–T04.35: **DONE**.

Key outcome: production research/evidence flow, provenance and second-hop controls, locked EvidenceSet, OriginalityPack, Knowledge Candidate admission, Obsidian mirror guard, isolated test database and final regression.

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

### Real O4 Angle + approval gates — PASS

- [x] real O4 ContentRun created through the approved path;
- [x] real `journal_input_bundle` created;
- [x] exact locked EvidenceSet/snapshot binding verified;
- [x] approved real model route used;
- [x] exact sanitized model input/model output provenance retained;
- [x] 4 materially usable Angle candidates produced;
- [x] MG content gate passed for human selection;
- [x] Founder selected exact `angle-01`;
- [x] exact durable AngleApproval persisted;
- [x] selected candidate hash revalidated;
- [x] approved-angle handoff verified;
- [x] identical approval retry reused the same approval ID;
- [x] upstream EvidenceSet/OriginalityPack/NeedHypothesis/bundle remained unchanged.

Locked selection:

```text
ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1
Angle artifact hash: e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
Selected Angle: angle-01
Candidate hash: 72ad8714e7d21cbcc04421f2141d8e2f4ead212ad8f674f21de122f19b622872
Working title: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

Approval closeout:

`docs/logs/2026-09-10-ce05-angle01-approval-closeout.md`

### Current gate — REAL O4 OUTLINE GATE

Owner: **MG Content Engine** for implementation/contract/editorial review.

Delegated local execution after this implementation PR is merged:

`docs/logs/2026-09-10-ce05-real-o4-outline-agent-local-task.md`

T05.10 status:

- [ ] **T05.10 Outline with evidence mapping — implementation in current PR; real runtime/content gate still pending.**

Implementation gate requires:

- [ ] exact approved `angle-01` is required; stale/wrong/conflicting approval fails closed;
- [ ] immutable/versioned `journal_outline` Artifact;
- [ ] exact bundle/EvidenceSet/OriginalityPack/Angle/AngleApproval bindings;
- [ ] primary answer explicitly precedes section structure;
- [ ] 3–8 meaningful sections with purpose and answer direction;
- [ ] factual sections require allowed Evidence refs;
- [ ] MOTGU-original sections require approved Originality refs;
- [ ] mixed sections require both;
- [ ] claim guards, reader movement and optional useful internal-link targets are explicit;
- [ ] unsupported/out-of-set refs fail closed;
- [ ] bounded structured model output validation;
- [ ] no research/tool calls;
- [ ] exact repeat reuses the same Outline artifact without another model call;
- [ ] focused tests + regression/lint/type/migration gates pass.

Real O4 Outline gate additionally requires:

- [ ] migration `20260910_0018` applied and registry verified;
- [ ] the real run's immutable SettingsSnapshot is unchanged;
- [ ] provider/model remains exactly the already-approved `codex_cli / gpt-5.6-luna` route from that snapshot;
- [ ] active `journal_outline:v1` prompt and `journal_outline_v1:v1` recipe are used and recorded in the Outline ContextManifest;
- [ ] one real Outline model execution produces a grounded, useful Outline;
- [ ] run returns to `waiting_approval` after Outline completion;
- [ ] identical second execution proves zero extra model call/artifact;
- [ ] MG editorial review = PASS.

Design note: because SettingsSnapshot is immutable for the run and this real run predates T05.10, the Outline step deliberately reuses the exact already-approved Angle provider/model route for provider/model selection. It does not mutate or replace the run SettingsSnapshot. Prompt/recipe identity is independently versioned and bound in the T05.10 ContextManifest.

### Critical path after real Outline PASS

- [ ] T05.11 Draft writer `vi-VN`.
- [ ] T05.12 Draft writer `en` independently from Vietnamese.
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
T05.10 implementation + CI
→ Founder merge
→ Agent Local real O4 Outline
→ MG reviews full Outline
→ if PASS: T05.11 + T05.12 VI/EN writers
→ T05.13 Review/Revise
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

- [ ] link Angle/Outline ModelCall `result_artifact_id` directly to the persisted output artifact or establish the equivalent canonical output-reference contract.

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
