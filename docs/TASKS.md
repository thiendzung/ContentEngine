# TASKS - ContentEngine delivery and progress

Delivery order: `PLAN.md`. Contract: `20-LOCAL-FIRST-DELIVERY-SPEC.md`. Current gate: `../AI_context.MD`. Detailed evidence belongs in `logs/`, not repeated UUID tables here. CE task IDs are retained; LF IDs organize delivery outcomes across them.

Maximum WIP: one implementation plus related local verification; one executor on the operational lineage. A planned task is not execution permission.

## Active delivery work

| ID | Owner | Scope | Dependency | State / acceptance |
|---|---|---|---|---|
| LF-00 | MG / Founder | Local-first spec, plan, task, checklist and roles | Founder decision | Defined by this change; effective on merge; no runtime completion implied |
| LF-01 | Agent Local / MG review | Read-only input verification and Angle blocker classification | LF-00 merged + Founder dispatch | NEXT, NOT EXECUTED; exact task in `logs/2026-09-12-lf01-local-angle-preflight-task.md` |
| LF-02 | MG + local verification | Smallest proven blocker resolution, regression if code changes | Reviewed LF-01 evidence | NOT STARTED; no speculative fix; permission issue may need no code |
| LF-03 | Agent Local / MG review | Resume same fresh lineage through authorized Journal steps | Verified inputs + cleared blocker + exact task/budget | NOT STARTED; stop at editorial gate or conclusive blocker |
| LF-04 | MG + Agent Local + Founder | Operational Package V0, checks, exact final approval | LF-03 artifacts | NOT STARTED; closes M1 with real local evidence |
| LF-05 | MG + Agent Local | Small operator path, diagnostics, runtime/test isolation, backup/restore | M1 pass; select observed need | BACKLOG; no new workflow engine |
| LF-06 | Agent Local / MG + Founder | Three distinct bilingual Journal cases total, including M1 | M1 + required LF-05 work | BACKLOG; last two on same merged version, no case-specific code; safe resume |
| LF-07 | MG + Founder | Manual placement + content/version/URL identity and observations | M1/M2 + explicit publishing decision | BACKLOG; no auto-publish or full CE08 completion claim |
| LF-08 | MG + Founder | Edit/failure feedback, Golden/Weak baseline, controlled changes | Real outputs/edits; audience claims need real observations | BACKLOG for automation; capture per-run evidence now |

## CE00-CE04 - retained completed foundation

CE00 Foundation Contracts, CE01 Repository/Research Spike/Walking Skeleton, CE02 Core Data/Settings (T02.1-T02.23), CE03 Durable Harness (T03.1-T03.20), CE04 Knowledge/Production Research (T04.1-T04.35): CLOSED / PASS per existing history. Do not rebuild.

CE01's historical Golden Journal reached human review; that is not evidence that the current fresh M1 lineage finished.

## CE05 - Journal Engine V1

Status: ACTIVE. M1 ONE REAL JOURNAL PASS: IN PROGRESS / not achieved.

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

Current checkpoint: `logs/2026-09-12-ce05-m1-one-real-journal-pass-status.md`. Runtime recovery selected FRESH_ACTIVE_DB; no repeat historical scan. Same fresh run/bundle, not a new candidate. Last report: 8 support claims / 3 readable sources; final input bindings need LF-01 verification. Angle was blocked before a model call; root cause remains unverified.

### M1 remaining acceptance

- [ ] Verify current EvidenceSet ID/version/hash, approved/locked state, metadata and bundle binding.
- [ ] Verify current OriginalityPack ID/hash, approved state and bundle binding.
- [ ] Classify and resolve Angle execution blocker without safety bypass.
- [ ] Valid generated and approved Angle on fresh lineage.
- [ ] Valid generated and approved Outline on fresh lineage.
- [ ] Complete final independent VI and EN visible content.
- [ ] Bounded Review/Revise complete.
- [ ] Both Assertion Audits non-fail, critical unsupported = 0, critical contradicted = 0.
- [ ] Both Source-copy checks fail_count = 0.
- [ ] All non-critical warnings preserved verbatim.
- [ ] T05.16 Operational Package V0 JSON + Markdown + hashes; pre-approval status explicit.
- [ ] Founder final approval bound to final content; canonical ContentVersion after approval.
- [ ] T05.17 One real Journal end-to-end on current local runtime.

### After M1, not its prerequisite

- [ ] T05.18 Critical Gate Regression - prioritize observed failures.
- [ ] T05.19 Resume / Replay Gate - prove on real local flow.
- [ ] T05.20 Human Review Surface - smallest useful surface first.
- [ ] T05.21 Metrics Baseline - edits, failures, calls, duration and known usage.
- [ ] T05.22 CE05 Closeout - not inferred from code coverage alone.

Before M1 no new provider/agent/framework, speculative abstraction, WordPress, automatic publishing/merge, repeated DB recovery, CI tuning without blocker or evaluator-version churn to rescue an article. Demonstrated security/data-integrity defects are the exception.

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

Status: NOT STARTED as full phase. LF-07 may take a small manual Journal handoff/identity slice before full CE06/CE07; it does not check off unimplemented adapters.

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
