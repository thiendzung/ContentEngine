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
| LF-04 | MG + Agent Local + Founder | Independent VI/EN through quality checks, Operational Package V0 and final approval | Persisted OutlineApproval | ACTIVE - LF-04A generation PASS; LF-04B quality PASS / MG ACCEPTED; LF-04C package PASS; mandatory Founder final content gate #3 APPROVED. LF-04D is active: persist exact final approvals + canonical approved bilingual ContentVersions, NO PUBLISH. Exact task `logs/2026-09-13-lf04d-founder-final-approval-content-version-task.md` |
| LF-05 | MG + Agent Local | Small operator path, diagnostics, runtime/test isolation, backup/restore | M1 pass; select observed need | BACKLOG; no new workflow engine |
| LF-06 | Agent Local / MG + Founder | Three distinct bilingual Journal cases total, including M1 | M1 + required LF-05 work | BACKLOG |
| LF-07 | MG + Founder | Manual placement + content/version/URL identity and observations | M1/M2 + explicit publishing decision | BACKLOG |
| LF-08 | MG + Founder | Edit/failure feedback, Golden/Weak baseline, controlled changes | Real outputs/edits | BACKLOG for automation; capture evidence now |

## CE00-CE04 - retained completed foundation

CE00 Foundation Contracts, CE01 Repository/Research Spike/Walking Skeleton, CE02 Core Data/Settings, CE03 Durable Harness, CE04 Knowledge/Production Research: CLOSED / PASS per existing history. Do not rebuild.

CE01's historical Golden Journal reached human review; that is not evidence that the current fresh M1 lineage finished.

## CE05 - Journal Engine V1

Status: ACTIVE. M1 ONE REAL JOURNAL PASS: final persistence/closeout in progress; no publishing authority granted.

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
- [x] T05.10 Evidence-mapped Outline implementation and historical proof.
- [x] T05.11 VI Writer implementation and historical proof.
- [x] T05.12 EN Writer implementation and bilingual-independence proof.
- [x] T05.13 Bounded Review/Revise implementation and historical proof.
- [x] Assertion Audit through generator/evaluator v5, schema 1; fail-closed hard types.
- [x] Source-copy v2; canonical audit pairs v3/v3, v4/v4, v5/v5 only; mixed pairs reject.
- [x] Focused retry/idempotency/recovery/provenance regression coverage.

Current checkpoint:

- canonical Angle + AngleApproval and persisted-approved Outline remain unchanged;
- final VI is immutable v3 `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`, hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`;
- VI Assertion Audit PASS; VI Source-copy PASS, `fail_count=0`, `warn_count=0`;
- final EN is immutable v4 `43007d23-8fbf-498d-ac49-436414c87aaf`, hash `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`;
- EN Assertion Audit PASS; EN Source-copy hard gate PASS, `fail_count=0`, `warn_count=2`;
- surviving warning 1: `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`;
- surviving warning 2: `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`;
- Operational Package V0 JSON SHA-256 `9d804da5c8d0756930b577e8e4244408cf9a8236d7b9205a8135d215e61b429a`;
- Operational Package V0 Markdown SHA-256 `a3804dd7622b9182c581b95aa2f892df2ee82a4e83c5c9a65f55ca802fa67c9f`;
- package generated deterministically, `not_published=true`, ModelCalls `14`, ToolCalls `0`;
- Founder explicitly approved exact VI + EN + both package hashes and accepted both EN warnings unchanged;
- Founder authorized approval persistence + canonical ContentVersion creation only; publish/WordPress remains forbidden.

### M1 remaining acceptance

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
- [x] T05.16 Operational Package V0 JSON + Markdown + SHA-256; pre-approval status explicit.
- [x] Mandatory human gate #3: Founder final approval bound to exact VI/EN + package hashes.
- [ ] Persist Founder approvals against exact final_content artifacts. ACTIVE LF-04D.
- [ ] Create/reuse canonical ContentItem + approved ContentVersion per locale via existing canonical path. ACTIVE LF-04D.
- [ ] Verify M1 durable closeout on current local runtime with no publish side effect.

### After M1, not its prerequisite

- [ ] T05.18 Critical Gate Regression - prioritize observed failures: foreign-script contamination, context-only factual support mismatch, late unsupported closing brand statements.
- [ ] T05.19 Resume / Replay Gate - prove on real local flow.
- [ ] T05.20 Human Review Surface - smallest useful Review Console first, based on actual operator friction.
- [ ] T05.21 Metrics Baseline - edits, failures, calls, duration and known usage.
- [ ] T05.22 CE05 Closeout - not inferred from code coverage alone.

Before M1: no new provider/agent/framework, speculative abstraction, WordPress automation, automatic publishing/merge, repeated DB recovery, CI tuning without a real blocker, or evaluator-version churn to rescue an article. Demonstrated security/data-integrity defects are the exception.

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
