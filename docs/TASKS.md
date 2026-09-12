# TASKS — ContentEngine V1

This file is the current roadmap and progress ledger. Detailed historical evidence belongs in `docs/logs/`.

Repository phase numbering here is authoritative for active work.

## Operating rule

Maximum active work:

```text
1 primary implementation task
+ 1 delegated local verification task
```

Local agents must synchronize their local repository to the exact GitHub ref before reading local task files or running local code. Do not activate the next task until the current semantic state is correct.

---

## CE00 — Foundation Contracts

Status: **CLOSED / PASS**.

---

## CE01 — Repository Skeleton + Research Spike + Walking Skeleton

Status: **CLOSED / PASS**.

Key outcome: one Golden Journal walking skeleton reached human review with zero critical unsupported assertions.

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

### M1 — ONE REAL JOURNAL PASS

Status: **IN PROGRESS**.

Goal:

> Prove one real MOTGU Journal candidate end-to-end before adding more infrastructure.

The CE05 North Star remains:

```text
selected opportunity
→ ContentCase + bounded inputs
→ approved angle
→ approved outline
→ independent VI/EN drafts
→ bounded revision
→ assertion/source checks
→ Operational Package
→ final human approval
```

### Completed implementation foundation

- [x] T05.1 ContentCase/LocaleVariant Journal UI.
- [x] T05.2 Internal knowledge recall.
- [x] T05.3 Content Memory overlap foundation.
- [x] T05.4 Discovery Research step.
- [x] T05.5 Opportunity Map selection handoff.
- [x] T05.6 Evidence Research + EvidenceSet step.
- [x] T05.7 OriginalityPack step.
- [x] T05.8 Angle generator structured output implementation.
- [x] T05.9 Angle approval state/runtime bridge implementation.
- [x] T05.10 Outline with evidence mapping implementation and prior real-runtime proof.
- [x] T05.11 Vietnamese Writer implementation and prior real-runtime proof.
- [x] T05.12 English Writer implementation and bilingual-independence proof.
- [x] T05.13 bounded Review/Revise implementation and prior real-runtime proof.
- [x] Assertion Audit production harness implemented and hardened through generator/evaluator v5, schema 1.
- [x] Structural non-assertive normalization remains fail-closed for required/assertive content.
- [x] Sentence-level bounded reader-guidance normalization merged in PR #63.
- [x] Source-copy v2 implemented.
- [x] Source-copy accepts only canonical Assertion Audit pairs v3/v3, v4/v4 and v5/v5; mixed pairs reject.
- [x] Important retry/idempotency/recovery/provenance paths have focused regression coverage.

Historical real O4 and pre-reset runtime evidence remains in `docs/logs/`. Those historical UUIDs are not prerequisites for the active M1 candidate when absent from the active runtime database.

### Active operating decision — fresh runtime acceptance

Canonical decision:

`docs/logs/2026-09-11-ce05-fast-operational-reset.md`

Rules:

- do not recreate old UUIDs;
- do not copy synthetic historical audit/evaluation rows;
- one cheap runtime recovery scan only;
- if no complete compatible lineage exists, use the active `contentengine` database and continue fresh;
- only hard quality/data-integrity/security failures stop the first operational Journal;
- non-critical warnings may proceed when preserved verbatim for Founder review.

The authorized recovery scan has now completed. No complete compatible current lineage was found elsewhere. Selected path is:

`FRESH_ACTIVE_DB`

Do not repeat historical database recovery unless Founder/MG explicitly reopens it.

### Active fresh M1 runtime checkpoint

Runtime:

```text
Database: localhost:5432/contentengine
Migration: 20260910_0022 (head)
main checkpoint before context update: debc0897e2f985e1d0662e9e594894e40401d1b8
```

Fresh planning/runtime lineage:

```text
ContentCase: f0bfbad7-c266-4de1-8fd4-a85ad206e6ce
NeedHypothesis: 604f4e5a-68b8-4503-997a-494eff79d448
ContentOpportunity: 83275ff5-19c8-4753-8c01-2135ad6c9dd1
HumanSelection: 4ea09a4d-fa71-444f-87b0-0368de809387
ContentExperiment: 7d8bbc52-1287-4f5c-b024-2686d5e7114d
SettingsSnapshot: 1169921c-a649-4f93-bf1a-f8daa2f15338
Settings hash: ebf8c32758311160e4c6d91d4bf6c6f59d9a9e97da7ba8af56f7f615373f9054
Journal ContentRun: a92f6f69-1c83-4aca-9a2f-e547dd15b85f
journal_input_bundle: d65aa864-e2fe-4c94-92f3-8d73ea89a8db
Bundle hash: a7f8f2a815c943963e8fc018a4888611f1cf696fc63992cdf226406f3c7441e0
Journal run state: waiting_approval
```

This is the active M1 candidate. Do not create another fresh Journal run merely because Angle execution is blocked.

### Fresh evidence status

- [x] first evidence pass executed;
- [x] first pass was insufficient;
- [x] one authorized targeted retry executed;
- [x] retry produced 8 support claims from 3 readable source documents;
- [ ] before Angle, read-only verify the final fresh EvidenceSet ID/version/hash/status/approval/lock state;
- [ ] before Angle, read-only verify the final fresh OriginalityPack ID/hash/status/approval state;
- [ ] verify both are the exact inputs bound to `journal_input_bundle d65aa864-e2fe-4c94-92f3-8d73ea89a8db`.

The last runtime report omitted the final EvidenceSet/OriginalityPack identifiers. Do not infer them. Verify them once, then proceed. If valid, do not research again.

### CURRENT GATE — REAL ANGLE EXECUTION

Status: **BLOCKED**.

Observed runtime evidence:

```text
Angle ModelCalls: 0
ContentEngine ToolCalls: 0
Current Journal ModelCalls: 0
Current Journal ToolCalls: 0
Angle artifact: none
Operational Package: none
```

Blocker:

`authorized Angle model execution was rejected by the local execution safety gate, including when separated from approval.`

Interpretation:

- this is the current smallest real bottleneck;
- it is not a DB-recovery blocker;
- it is not an Evidence sufficiency blocker unless the read-only binding verification fails;
- it is not an Assertion Audit or Source-copy blocker;
- no synthetic Angle candidate or safety bypass is allowed.

### Immediate sequence

```text
read-only verify fresh EvidenceSet + OriginalityPack bindings
→ identify the exact reason the authorized Angle execution safety gate rejects the run
→ fix only the smallest proven invocation/code defect if one exists
→ reuse SAME ContentRun + SAME journal_input_bundle
→ Angle generation
→ pre-authorized deterministic Angle selection + AngleApproval
→ Outline
→ independent VI + EN writers
→ bounded Review/Revise
→ Assertion Audit v5 for both locales
→ require audit_result != fail and critical counts = 0
→ Source-copy v2 for both locales
→ require fail_count = 0
→ Operational Package V0 JSON + Markdown + SHA-256
→ Founder final operational approval
→ M1 — ONE REAL JOURNAL PASS
```

### M1 progress

```text
Runtime DB resolution       PASS
Fresh planning spine        PASS
Evidence research           PASS — 8 supports / 3 readable docs
EvidenceSet/Originality     VERIFY CURRENT BINDINGS BEFORE ANGLE
Journal input bundle        PASS
Angle                       BLOCKED — CURRENT GATE
Outline                     NOT STARTED on fresh candidate
VI/EN Writer                NOT STARTED on fresh candidate
Review/Revise               NOT STARTED on fresh candidate
Assertion Audit v5          NOT STARTED on fresh candidate
Source-copy v2              NOT STARTED on fresh candidate
T05.16 Final Package        NOT STARTED
Founder final approval      NOT STARTED
T05.17 One Real Journal     NOT ACHIEVED
```

### M1 hard exit criteria

M1 can be marked PASS only when one fresh real candidate has:

- [ ] a valid approved Angle;
- [ ] a valid approved Outline;
- [ ] complete final VI visible content;
- [ ] complete final EN visible content;
- [ ] bounded Review/Revise complete;
- [ ] VI Assertion Audit result not `fail`, critical unsupported = 0, critical contradicted = 0;
- [ ] EN Assertion Audit result not `fail`, critical unsupported = 0, critical contradicted = 0;
- [ ] VI Source-copy `fail_count = 0`;
- [ ] EN Source-copy `fail_count = 0`;
- [ ] every non-critical warning preserved verbatim;
- [ ] deterministic Operational Package V0 JSON + Markdown with SHA-256;
- [ ] Founder final operational approval.

### T05.16 / T05.17

- [ ] T05.16 Final content package — **NOT YET ACHIEVED ON THE FRESH M1 CANDIDATE**.
- [ ] T05.17 One real MOTGU Journal end-to-end candidate — **NOT YET ACHIEVED**.

### Post-M1 hardening

Keep after the first real Journal unless a demonstrated safety/data-integrity issue requires earlier work:

- [ ] T05.18 Critical Gate Regression.
- [ ] T05.19 Resume / Replay Gate.
- [ ] T05.20 Human Review Surface.
- [ ] T05.21 CE05 Metrics Baseline.
- [ ] T05.22 CE05 Closeout.

### Critical-path rule until M1 PASS

Every new task must directly shorten or unblock:

`Angle → Outline → VI/EN → Review → Audit → Source-copy → Package → Founder approval`

Otherwise backlog it.

Before M1 PASS:

- [ ] no new provider;
- [ ] no new agent role;
- [ ] no generic workflow builder;
- [ ] no architecture redesign;
- [ ] no speculative abstraction;
- [ ] no automated publishing;
- [ ] no WordPress work;
- [ ] no automated merge;
- [ ] no CI optimization unless CI itself becomes a demonstrated blocker;
- [ ] no Assertion Audit v6 unless Founder/MG explicitly reopens the contract after a final hard failure.

Canonical current M1 checkpoint:

`docs/logs/2026-09-12-ce05-m1-one-real-journal-pass-status.md`

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
