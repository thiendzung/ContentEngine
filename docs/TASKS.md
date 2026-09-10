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

### Real O4 Angle Gate — PASS FOR HUMAN SELECTION

Real runtime evidence:

- [x] real O4 ContentRun created through the approved path;
- [x] real `journal_input_bundle` created;
- [x] exact locked EvidenceSet/snapshot binding verified;
- [x] approved real model route used;
- [x] exact sanitized model input provenance retained;
- [x] model output provenance retained;
- [x] 4 schema-valid, materially usable Angle candidates produced;
- [x] important factual premises bounded by allowed evidence;
- [x] no invented MOTGU/business fact identified in MG gate review;
- [x] Angles address the real first-time-buyer price question;
- [x] no generic filler blocker identified;
- [x] MG review = PASS FOR HUMAN SELECTION;
- [x] Founder selected one exact Angle without infrastructure/code changes.

Founder decision on 2026-09-10: **`angle-01`**.

Selected working title: `A First-Time Buyer’s Checklist for Understanding an Artwork’s Price`.

Decision/evidence log:

`docs/logs/2026-09-10-ce05-real-o4-angle-selection.md`

### Current gate — ANGLE-01 APPROVAL PERSISTENCE

Owner: **Agent Local**, exact delegated runtime/database task only.

Task:

`docs/logs/2026-09-10-ce05-angle01-approval-agent-local-task.md`

Gate is PASS only when:

- [ ] exactly one AngleApproval exists for Angle artifact `854d4f34-22c0-4a9e-8d00-0f7f9461036d` v1 / exact hash;
- [ ] selected candidate is exactly `angle-01`;
- [ ] selected candidate hash is persisted and revalidated;
- [ ] `approved_by=founder` with the locked approval reason;
- [ ] approved-angle handoff verifies the same artifact/candidate snapshot;
- [ ] identical retry reuses the same approval ID;
- [ ] no model/provider/tool call is added;
- [ ] EvidenceSet, OriginalityPack and NeedHypothesis remain unchanged;
- [ ] MG reviews the persistence evidence before T05.10 starts.

### Critical path after approval persistence

- [ ] T05.10 Outline with evidence mapping. **PREPARED / BLOCKED ON ANGLE APPROVAL**
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

Prepared T05.10 contract:

`docs/logs/2026-09-10-ce05-t05-10-outline-mg-task.md`

### Immediate sequence

```text
Founder selected angle-01
→ persist exact AngleApproval
→ verify approved-angle handoff
→ MG closes approval gate
→ T05.10 Outline
→ T05.11 + T05.12 VI/EN drafts
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

- [ ] link Angle ModelCall `result_artifact_id` directly to the persisted Angle artifact or establish the equivalent canonical output-reference contract.

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
