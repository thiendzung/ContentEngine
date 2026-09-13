# TASKS - ContentEngine delivery and progress

Delivery order: `PLAN.md`. Contract: `20-LOCAL-FIRST-DELIVERY-SPEC.md`. Current gate: `../AI_context.MD`. Detailed evidence belongs in `logs/`, not repeated UUID tables here. CE task IDs are retained; LF IDs organize delivery outcomes across them.

Maximum WIP: one implementation plus related local verification; one executor on the operational lineage. A planned task is not execution permission.

## Active delivery work

| ID | Owner | Scope | Dependency | State / acceptance |
|---|---|---|---|---|
| LF-00 | MG / Founder | Local-first spec, plan, task, checklist and roles | Founder decision | DONE - merged in main; no runtime completion implied |
| LF-01 | Agent Local / MG review | Read-only input verification and Angle blocker classification | LF-00 merged + Founder dispatch | DONE / REVIEWED - inputs reusable; blocker classified OUTER_EXECUTION_POLICY |
| LF-02 | MG + Founder + Agent Local verification | Safe Angle execution and first human gate on exact fresh lineage | LF-01 reviewed | DONE / REVIEWED - canonical Angle generated, `angle-01` selected, AngleApproval persisted |
| LF-03 | Founder + Agent Local / MG review | Generate one grounded Outline and persist the second human gate | Valid approved Angle | DONE / REVIEWED - canonical Outline + exact OutlineApproval persisted |
| LF-04 | MG + Agent Local + Founder | Independent VI/EN through final approval and canonical ContentVersions | Persisted OutlineApproval | DONE / REVIEWED - M1 real bilingual Journal lineage complete through approved ContentVersions, no publish. Closeout: `logs/2026-09-13-m1-journal-closeout.md` |
| LF-05 | MG + Agent Local | Smallest useful operator path / Human Review Surface + production board | M1 pass | DONE / REVIEWED - T05.20A/B and T05.21A/B proven on M1 runtime; read model, actions and production board available |
| LF-06 | Agent Local / MG + Founder | Three distinct bilingual Journal cases total, including M1 | M1 + required LF-05 work | BACKLOG |
| LF-07 | MG + Founder | Manual placement + content/version/URL identity and observations | M1/M2 + explicit publishing decision | BACKLOG |
| LF-08 | MG + Founder | Edit/failure feedback, Golden/Weak baseline, controlled changes | Real outputs/edits | BACKLOG for automation; capture evidence now |

## CE00-CE04 - retained completed foundation

CE00 Foundation Contracts, CE01 Repository/Research Spike/Walking Skeleton, CE02 Core Data/Settings, CE03 Durable Harness, CE04 Knowledge/Production Research: CLOSED / PASS per existing history. Do not rebuild.

CE01's historical Golden Journal reached human review; that is not the M1 proof. M1 is now proven by the fresh real local lineage closed on 2026-09-13.

## CE05 - Journal Engine V1

Status: ACTIVE post-M1 hardening/operator usability. **M1 ONE REAL JOURNAL PASS: COMPLETE / CLOSED.**

Implementation foundation retained:

- [x] T05.1 ContentCase/LocaleVariant Journal surface.
- [x] T05.2 Approved internal knowledge recall.
- [x] T05.3 Content Memory overlap foundation.
- [x] T05.4 Discovery Research.
- [x] T05.5 Opportunity selection handoff.
- [x] T05.6 Evidence Research and EvidenceSet.
- [x] T05.7 OriginalityPack.
- [x] T05.8 Structured Angle generator.
- [x] T05.9 Angle approval/runtime bridge.
- [x] T05.10 Evidence-mapped Outline implementation and real M1 proof.
- [x] T05.11 VI Writer implementation and real M1 proof.
- [x] T05.12 EN Writer implementation and bilingual-independence proof.
- [x] T05.13 Bounded Review/Revise implementation and real recovery evidence.
- [x] Assertion Audit through generator/evaluator v5, schema 1; fail-closed hard types.
- [x] Source-copy v2; canonical audit pairs v3/v3, v4/v4, v5/v5 only; mixed pairs reject.
- [x] Focused retry/idempotency/recovery/provenance regression coverage.
- [x] T05.16 Operational Package V0 JSON + Markdown + SHA-256.
- [x] Mandatory human gate #3: Founder final approval bound to exact VI/EN + package hashes.
- [x] Canonical ContentItem + approved ContentVersion per locale persisted through existing path.

### M1 closeout evidence

- Merged/local finalization ref `8454e9fd3e2002901bea12c045826b1a5eac3b6d`.
- ContentCase `f0bfbad7-c266-4de1-8fd4-a85ad206e6ce`.
- VI approved ContentVersion `66ad367f-99af-4b37-8914-5b446fca50dd`, v1, final hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`.
- EN approved ContentVersion `6dcc3b6a-a507-47fd-8461-e0f084427f2e`, v1, final hash `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`.
- Both Writer runs completed after final approval persistence.
- VI Assertion Audit hard-clean; VI Source-copy `fail_count=0`, `warn_count=0`.
- EN Assertion Audit hard-clean; EN Source-copy `fail_count=0`, `warn_count=2`.
- Accepted warning 1: `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`.
- Accepted warning 2: `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`.
- Operational Package JSON SHA-256 `9d804da5c8d0756930b577e8e4244408cf9a8236d7b9205a8135d215e61b429a`.
- Operational Package Markdown SHA-256 `a3804dd7622b9182c581b95aa2f892df2ee82a4e83c5c9a65f55ca802fa67c9f`.
- ModelCalls remained `14`; ToolCalls remained `0` through finalization.
- published ContentVersions `0`; no PublishedContent, PublishEvent, URL mapping or WordPress/external publish action.

Detailed evidence: `logs/2026-09-13-m1-journal-closeout.md`.

### M1 acceptance — COMPLETE

- [x] Verify current EvidenceSet ID/version/hash, approved/locked state, metadata and bundle binding.
- [x] Verify current OriginalityPack ID/hash, approved state and bundle binding.
- [x] Valid generated and approved Angle on fresh lineage.
- [x] Valid generated and persisted-approved Outline on fresh lineage.
- [x] Generate independent VI and EN Writer content on fresh lineage.
- [x] VI bounded Review/Revise + authorized deterministic cleanup complete.
- [x] EN bounded Review/Revise + authorized deterministic cleanup complete.
- [x] Both final Assertion Audits hard-clean.
- [x] Both final Source-copy checks `fail_count = 0`.
- [x] Final independent VI/EN visible content reviewed and MG accepted.
- [x] All surviving warnings preserved verbatim.
- [x] T05.16 Operational Package V0 deterministic JSON + Markdown + SHA-256.
- [x] Founder final approval bound to exact final content/package.
- [x] Founder approvals persisted against exact final_content artifacts.
- [x] Canonical ContentItem + approved ContentVersion per locale created through existing canonical path.
- [x] M1 durable closeout verified on current local runtime with no publish side effect.

### Current post-M1 slices

- [x] T05.20A Human Review Surface — read-only Review Console over persisted truth; proven end-to-end on M1 runtime.
- [x] T05.20B Approval actions — Approve / Request revision / Reject with durable existing contracts; UI Vietnamese-first.
- [x] T05.21A Production Board — ContentCase-centric board with five operating lanes and Codex coordinator projection.
- [x] T05.21B Production Board UX — exact case deep-link, viewport fit, compact operator layout and meaningful execution labels; final local proof PASS.
- [x] T05.22A Operational Observability Baseline — DONE / VERIFIED. Safe structured logs, local DEBUG default, production-safe clamp, request correlation and total-log Uvicorn query redaction proven on runtime.
- [x] T05.22B Durable Delegation Telemetry — DONE / VERIFIED / MERGED. Persisted `Codex -> subagent/application/tool` execution hierarchy, idempotent lifecycle and Production Board projection; isolated TEST DB proof passed without mutating M1.
- [ ] T05.22C Controlled Codex Delegation Bridge — ACTIVE. Require exact completed Codex delegation-plan ModelCall + immutable plan Artifact + immutable SettingsSnapshot route + exact runner version before one approved child worker may execute. Exact task `logs/2026-09-13-t05-22c-controlled-delegation-bridge-task.md`.

### Required post-M1 hardening, not blockers for T05.22C

- [ ] T05.18 Critical Gate Regression - observed failures only: foreign-script contamination, context-only factual support mismatch, late unsupported closing brand statements.
- [ ] T05.19 Resume / Replay Gate - prove on real local flow.
- [ ] T05.23 Metrics Baseline - edits, failures, calls, duration and known usage. Renumbered from historical T05.21 after Production Board occupied T05.21A/B.
- [ ] T05.24 CE05 Closeout - not inferred from M1 alone; follows post-M1 hardening/pilot evidence. Renumbered from historical T05.22.

Do not turn M1 friction into a new provider/agent/framework or speculative workflow engine. Prefer small changes proven by real operator pain.

## CE06 - Full Quality + Golden Regression

Status: NOT STARTED as full phase. Small failure regressions do not imply completion.

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

## CE07 - Artwork Engine V1

Status: NOT STARTED; not opened by this plan.

- [ ] T07.1 WordPress/WooCommerce canonical Artwork adapter.
- [ ] T07.2 Artwork fact lock.
- [ ] T07.3 MediaAsset ingest/ref mapping.
- [ ] T07.4 MediaObservation workflow + approval status.
- [ ] T07.5 Artist context retrieval.
- [ ] T07.6 Artist-intent provenance rule.
- [ ] T07.7 Artwork OriginalityPack.
- [ ] T07.8 Artwork writer vi-VN.
- [ ] T07.9 Artwork writer en.
- [ ] T07.10 Artwork Assertion Audit.
- [ ] T07.11 Related content linker.
- [ ] T07.12 Artwork quality gates.
- [ ] T07.13 One real MOTGU Artwork candidate.

## CE08 - WordPress Draft + Measurement Foundation

Status: NOT STARTED as full phase. LF-07 may take a small manual Journal handoff/identity slice before full CE06/CE07.

- [ ] T08.1 WordPress draft publish adapter.
- [ ] T08.2 ContentItem to WordPress ID mapping.
- [ ] T08.3 ContentVersion PublishEvent history.
- [ ] T08.4 Idempotency/outbox/reconciliation.
- [ ] T08.5 Search Console adapter.
- [ ] T08.6 Analytics adapter.
- [ ] T08.7 MOTGU conversion-event mapping.
- [ ] T08.8 Normalize core PerformanceMetric values.
- [ ] T08.9 Preserve raw provider PerformanceSnapshot privately.
- [ ] T08.10 Rank Math signal feasibility spike.
- [ ] T08.11 Content hypothesis to metrics traceability.
- [ ] T08.12 Feed real Search Console queries into Discovery signals, not automatic strategy changes.

## CE09 - Content Memory + Learning

Status: NOT STARTED as full phase. Collect useful run/edit records now; automate by evidence.

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
- [ ] T09.13 Compare planned questions with real queries and update signal strength.

## CE10 - Pilot

Status: NOT STARTED.

- [ ] T10.1 Define 10-20 content hypotheses.
- [ ] T10.2 Balance pillar/cluster and Journal/Artwork.
- [ ] T10.3 Run production pilot.
- [ ] T10.4 Review quality failures.
- [ ] T10.5 Review human editing burden.
- [ ] T10.6 Review provider cost/quality and redundant calls.
- [ ] T10.7 Review cost/latency overall.
- [ ] T10.8 Promote first stable Golden Set.
- [ ] T10.9 Review audience signals and evidence strength.
- [ ] T10.10 Decide next roadmap only from pilot evidence.