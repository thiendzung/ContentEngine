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
- [x] T05.13 bounded Review/Revise — implementation + real bilingual runtime/content/provenance/idempotency gate PASS.

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

NeedHypothesis `530bdd27-f008-4910-9b3b-df83e007cfa2` remains `PROPOSED`.

### T05.11/T05.12 real Writer closeout

Exact real Writer v1 outputs:

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

Writer gate proved exact support/provenance, bilingual independence, no sibling/translation input, ToolCalls=0, exact rerun reuse and upstream immutability. The five EN v1 entries were accepted safety absence notes, not asserted unsupported facts. Zero unresolved was correctly enforced at T05.13 exit rather than T05.11/T05.12 exit.

Canonical decision:

`docs/logs/2026-09-10-ce05-writer-gate-contract-correction.md`

### T05.13 real Review/Revise closeout

Canonical closeout:

`docs/logs/2026-09-10-ce05-t05-13-real-gate-closeout.md`

Exact revised outputs entering T05.14:

```text
vi-VN Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
vi-VN source v1: 19c2c580-efb6-43ba-b1a9-0625f0804ede / 972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6
vi-VN revised v2: a0afa7d0-af3d-4669-ae18-54c54b87731f / da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
vi-VN v2 unresolved count: 0

en Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
en source v1: fdf54b59-92d3-4c42-ac14-e5a7ada26837 / cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495
en revised v2: d512f3f4-bc28-473b-9de1-f0a838940191 / e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
en v2 unresolved count: 0
```

Real T05.13 gate proved:

- [x] local main synchronized exactly to the merged T05.13 implementation;
- [x] migration `20260910_0020` and exact VI/EN review/revise registry verified;
- [x] source v1 IDs/versions/hashes and full upstream lineage revalidated;
- [x] same existing locale Writer `localize` runs reused; no new ContentRun;
- [x] one real bounded review/revise model flow per locale;
- [x] exact Outline section IDs/order and Evidence/Originality refs preserved;
- [x] no sibling draft, translation, research, Search, URL or ToolCall input;
- [x] no missing artwork/artist/commerce/comparison/market fact invented;
- [x] one immutable v2 created per locale; source v1 remained immutable;
- [x] document-level and section-level `unresolved_factual_claims` all equal `[]`;
- [x] both Writer runs returned to `waiting_approval`;
- [x] exact reruns reused the same v2 artifacts with `model_attempts=0` and zero further side effects;
- [x] EvidenceSet, OriginalityPack, selected Angle, accepted Outline, SettingsSnapshot, NeedHypothesis and source O4 artifacts remained unchanged;
- [x] MG reviewed both full v2 drafts against v1, Outline, Evidence and Originality boundaries and marked T05.13 **PASS**.

### T05.14 FINAL CLOSEOUT / CURRENT GATE — T05.15 BASIC SOURCE-COPY

Owner: **MG Content Engine** for implementation/contract/review; Agent Local executes only the exact post-merge real runtime gate.

Merged T05.14 Assertion Audit implementation through PR #46 includes:

- [x] exact immutable VI/EN v2 input binding and hash revalidation;
- [x] deterministic visible-copy segmentation;
- [x] bounded model assertion extraction/classification only — no rewrite;
- [x] exact-substring validation for each assertion;
- [x] location-bounded Evidence/Originality refs;
- [x] persisted Evidence ID → Claim ID mapping in code;
- [x] deterministic critical unsupported/contradicted escalation for factual/brand/artist-intent/visual/live assertions;
- [x] immutable `assertion_audit` Artifact + deterministic `QualityEvaluation` persistence using existing contracts;
- [x] exact audit fingerprint/reuse contract;
- [x] independent VI/EN prompt/recipe registry in migration `20260910_0021`;
- [x] approved local-agent runtime bridge with no tools/research/sibling draft;
- [x] production CLI + focused tests;
- [x] exact Agent Local task with mandatory local Git synchronization before task read/execution.
- [x] bounded EN post-audit revision step in the existing Writer `localize` run;
- [x] exact persisted five-finding binding and deterministic non-target immutability;
- [x] immutable EN `journal_draft` v3 with exact rerun reuse;
- [x] post-merge EN revision → Assertion Audit v3 re-audit task executed;
- [x] deterministic deletion of the sole EN v3 `closing:3` unsupported critical sentence;
- [x] immutable EN `journal_draft` v4 in the same Writer run with cleanup idempotency;
- [x] post-merge EN v4 cleanup → Assertion Audit v3 re-audit completed with T05.14 PASS.

Post-merge real Assertion Audit task:

`docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`

T05.14 real v3 status:

- [x] **T05.14 Assertion Audit — VI PASS / EN final cleanup and re-audit PASS.**

T05.14 final cleanup implementation and production re-audit are complete. The exact
English v4 artifact and PASS audit remain immutable inputs for later gates; the VI PASS
artifact and all shared upstream records remain immutable.

Real T05.14 v3 gate evidence:

- [x] local `main` synchronized exactly to merged T05.14 implementation before the real task;
- [x] BOTH exact locale sources preflighted before auditing either locale;
- [x] migration `20260910_0021` + exact VI/EN assertion-audit prompt/recipe registry verified;
- [x] real VI assertion audit executed against exact v2 snapshot;
- [x] real EN assertion audit executed against exact v2 snapshot;
- [x] one `assertion_audit` Artifact and one deterministic hard-gate `QualityEvaluation` per locale;
- [x] every required standfirst/lead/body/closing segment audited, with title/headings explicitly accounted for;
- [x] assertion text remains an exact substring of its source segment;
- [x] Evidence/Originality refs remain within exact location support boundaries;
- [x] Evidence refs map to persisted Claim IDs through code;
- [x] VI `audit_result=pass`, `critical_unsupported_count=0`, `critical_contradicted_count=0`;
- [x] EN `audit_result=pass`, `critical_unsupported_count=0`, `critical_contradicted_count=0`;
- [x] the two EN attention items are explicitly classified rather than silently treated as external factual proof;
- [x] no research/Search/URL/ToolCall, sibling draft or translation input;
- [x] exact reruns reuse the same audit artifacts/evaluations with `model_attempts=0` and zero further side effects;
- [x] source v2 drafts and all upstream lineage remain immutable;
- [x] EN v3 re-audit completed and the sole remaining finding is `closing:3` unsupported critical `brand_statement`;
- [x] deterministic EN v4 cleanup completes with zero ModelCalls/ToolCalls;
- [x] EN v4 `audit_result=pass`, unsupported=0, contradicted=0;
- [x] MG reviews the full final EN v4 cleanup/re-audit output and marks T05.14 PASS.

If an audit completes as `warn` or `fail`, Agent Local returns `NEEDS CHANGES` and does not rewrite the content. Infrastructure/provenance/schema mismatches remain fail-closed `BLOCKED`.

### Current gate — T05.15 BASIC SOURCE-COPY / LEGACY VI PREFLIGHT COMPATIBILITY

Owner: **Agent Local** implements the bounded deterministic gate and its exact legacy
VI source-run compatibility; MG reviews the implementation and Founder controls merge.
Production T05.15 is not executed in the implementation task.

The first post-merge real preflight stopped before creating source-copy records because
the exact accepted T05.14 VI v2 source Writer is terminal `failed`. T05.15 must reuse
the existing T05.14 eligibility exception for that one immutable source lineage and
continue rejecting arbitrary failed/cancelled/completed source Writer runs.

- [ ] deterministic exact contiguous normalized-token overlap only;
- [ ] locked EvidenceSet excerpts and approved OriginalityPack text fields only;
- [ ] exact T05.14 source-writer eligibility reused without resurrecting the failed VI run;
- [ ] dedicated locale `eval` ContentRun with immutable handoff, check Artifact and
  deterministic QualityEvaluation;
- [ ] exact completed rerun reuses all outputs with zero side effects;
- [ ] post-merge real task:
  `docs/logs/2026-09-10-ce05-t05-15-real-source-copy-agent-local-task.md`;
- [ ] T05.15 real VI/EN gate after implementation merge.

No model/provider/tool/research/vector/fuzzy/translation similarity is in scope.
T05.16 remains NOT STARTED until both locales pass the real T05.15 gate.

### Critical path after T05.15 PASS

- [ ] T05.16 Final content package.
- [ ] T05.17 One real MOTGU Journal end-to-end candidate.
- [ ] T05.18 Critical Gate Regression.
- [ ] T05.19 Resume / Replay Gate.
- [ ] T05.20 Human Review Surface.
- [ ] T05.21 CE05 Metrics Baseline.
- [ ] T05.22 CE05 Closeout.

### Immediate sequence

```text
T05.15 basic source-copy implementation + final CI/review
→ Founder merge
→ Agent Local runs deterministic VI/EN source-copy check and exact reruns
→ MG reviews exact findings/provenance and marks T05.15 PASS
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
