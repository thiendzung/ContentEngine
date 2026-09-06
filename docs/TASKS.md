# TASKS — CONTENTENGINE V1

## CE00 — Foundation Contracts

- [x] T00.1 Initialize canonical README.
- [x] T00.2 Define North Star.
- [x] T00.3 Define non-negotiables.
- [x] T00.4 Define canonical architecture.
- [x] T00.5 Define core data contract.
- [x] T00.6 Define settings/Brand/Language contract.
- [x] T00.7 Define durable harness.
- [x] T00.8 Define memory/learning contract.
- [x] T00.9 Define quality/eval contract.
- [x] T00.10 Define Journal spec.
- [x] T00.11 Define Artwork spec.
- [x] T00.12 Define publish/measure spec.
- [x] T00.13 Add AGENTS.md governance.
- [x] T00.14 Final cross-document consistency review.

Status: **CLOSED**.

---

## CE01 — Repository Skeleton + Research Spike + Walking Skeleton

Status: **ACTIVE**.

### PR-A — Repository Skeleton

Status: **CLOSED / MERGED**.

PR: `#3 — CE01 PR-A — repository skeleton`

Merge commit: `8e16c2817359191d0c4cd2e45a28f7eba8fa1a19`

### Repository

- [x] T01.1 Create branch `ce01-walking-skeleton` from clean main.
- [x] T01.2 Create backend FastAPI package.
- [x] T01.3 Create frontend Next.js shell tối thiểu.
- [x] T01.4 Add root developer scripts.
- [x] T01.5 Add `.env.example`, never secrets.
- [x] T01.6 Add PostgreSQL connection + migration framework.
- [x] T01.7 Add module directories matching Architecture Spec, including `research/`.
- [x] T01.8 Add health/version endpoint.
- [x] T01.9 Add backend lint/type/test baseline.
- [x] T01.10 Add frontend lint/type/build baseline.
- [x] T01.11 Add OpenAPI generation + generated frontend types.
- [x] T01.12 Add CI required checks.
- [x] T01.13 Verify clean install from fresh checkout.

PR-A verification: backend install/lint/typecheck/migration/tests/OpenAPI and frontend install/type generation/lint/typecheck/build đều PASS trước merge.

### PR-B — Research/Search spike

Status: **CLOSED / PASS**.

- [x] T01.14 Add provider config/secret references for Serper, Tavily, Exa, Jina; Brave optional only.
- [x] T01.15 Add SearchProvider seam and minimal Serper discovery adapter.
- [x] T01.16 Add minimal Tavily/Exa source-discovery adapters or one common source-discovery seam proven with both providers.
- [x] T01.17 Add Jina selected-URL reader adapter.
- [x] T01.18 Store raw research result as bounded artifact with provider/query/source refs; do not write raw SERP payload to Obsidian.
- [x] T01.19 Add one-step second-hop extraction: cited URL/expert/report candidates from a selected source.
- [x] T01.20 Add manual Deep Research import shape: report + original source URLs; report itself is not factual authority.
- [x] T01.21 Add provider budget/stop-when-sufficient rule for the spike.

### PR-C — Opportunity Map Mini

Status: **CLOSED / MERGED**. Keyword Plan remains a supporting tool in Research.

PR: `#6 — CE01 PR-C — opportunity map mini`

Merge commit: `cda4f738aff08abf827e2ce49418ea29f5af351f`

- [x] Normalize MARKET/SEARCH/MOTGU Signal with scope, observation, provenance and dedupe.
- [x] Create NeedHypothesis with support/contradiction/alternatives/missing evidence.
- [x] Keep founder-proposed seeds PROPOSED until reviewed evidence supports a change.
- [x] Build ContentOpportunity editorial contract + existing-content decision.
- [x] Suggest Journal pillar/cluster or Artwork without creating new Artist/Visit engines.
- [x] Preserve human selection record and draft ContentExperiment measurement plan.

- [x] T01.22 Collect MARKET/SEARCH signals for one founder-proposed NeedHypothesis.
- [x] T01.23 Normalize + dedupe query/question signals.
- [x] T01.24 Classify question type, intent, audience stage and problem/desire with confidence.
- [x] T01.25 Build simple clusters by problem + intent + answer overlap, not string similarity only.
- [x] T01.26 Produce pillar/cluster candidates.
- [x] T01.27 Produce Niche Candidates with MOTGU Right-to-Win reason.
- [x] T01.28 Produce content decision: CREATE/UPDATE/REFRESH/MERGE/LINK_ONLY/DO_NOT_WRITE.
- [x] T01.29 Produce priority: NOW/NEXT/LATER/NO with short reasons; no fake 0–100 precision.
- [x] T01.30 Human review one Opportunity Map and select one opportunity for the Golden Journal.

PR-C evidence: canonical Research artifact `ce01-research-spike-20260906T013152Z.json` produced 34 signals. Final cleaned map produced 9 questions, 4 clusters and 4 opportunities with the unsupported broad Pillar removed. Founder selected `price` (`opp_ea484183ba36c6b2`). Selected artifact `ce01-opportunity-map-20260906T020602Z.json` records HumanSelection and ContentExperiment draft `exp_cdc69b59a413393c`; NeedHypothesis remains `PROPOSED`. At PR-C closeout no MOTGU-owned material had yet been attached; PR-D supplies that bounded content input.

### PR-D — Content Input

Status: **PASS / READY FOR REVIEW**.

- [x] T01.31 Collect 3–5 approved positive MOTGU excerpts for first locale.
- [x] T01.32 Collect 3–5 approved negative examples for first locale.
- [x] T01.33 Define short human editorial review form.
- [x] T01.34 Define one MOTGU ContentCase from selected ContentOpportunity.
- [x] T01.35 Define one real LocaleVariant.
- [x] T01.36 Build selected/manual EvidenceSet from higher-quality sources, not default Google top 1–5.
- [x] T01.37 Build Manual OriginalityPack.

PR-D evidence: `docs/13-CE01-CONTENT-INPUT-PRICE.md` records 4 founder-approved positive English examples, 4 founder-approved negative examples, the human editorial review form, ContentCase `cc_ce01_price_001`, English LocaleVariant `lv_ce01_price_en_001`, locked EvidenceSet `es_ce01_price_v1`, and approved OriginalityPack `opack_ce01_price_v1`. Founder decision on `2026-09-06`: `APPROVE CALIBRATION + CONTENT DIRECTION`. The approved scope is limited to helping a first-time buyer understand/evaluate a displayed artwork price; it does not claim an exact MOTGU/artist pricing formula. NeedHypothesis remains `PROPOSED`.

### Walking Skeleton

- [ ] T01.38 Implement/manual-drive Angle step.
- [ ] T01.39 Implement/manual-drive Outline step.
- [ ] T01.40 Implement Draft step through ModelRouter seam or temporary single adapter.
- [ ] T01.41 Add basic assertion audit.
- [ ] T01.42 Run human editorial review.
- [ ] T01.43 Record research/content failure notes without auto-changing contract.
- [ ] T01.44 Gate: decide whether Research + Opportunity Map + content contract is good enough for CE02.

### CE01 exit gate

- [x] Repo build/test clean.
- [x] One founder-proposed NeedHypothesis + real signals produces a readable Opportunity Map.
- [x] Human selects at least one opportunity with clear audience/problem/MOTGU advantage.
- [x] Selected research/evidence sources are demonstrably better than blindly taking Google top results.
- [ ] One real Journal reaches human review.
- [ ] Zero critical unsupported assertion in the reviewed candidate.

---

## CE02 — Core Data + Settings

- [ ] T02.1 Implement Project.
- [ ] Implement Signal, NeedHypothesis, ContentOpportunity and ContentExperiment contracts;
      do not create legacy ProblemDesire/AudienceSignal models. Update ContentCase refs.
- [ ] T02.2 Implement ContentCase.
- [ ] T02.3 Implement LocaleVariant.
- [ ] T02.4 Implement ContentItem/ContentVersion.
- [ ] T02.5 Implement SettingsVersion/SettingsSnapshot.
- [ ] T02.6 Implement Prompt/Recipe Registry.
- [ ] T02.7 Implement Brand DNA/Language DNA validation.
- [ ] T02.8 Implement Calibration Example storage.
- [ ] T02.9 Implement Source/SourceDocument/KnowledgeChunk.
- [ ] T02.10 Implement Entity/Claim/Evidence/EvidenceSet.
- [ ] T02.11 Implement OriginalityPack.
- [ ] T02.12 Implement MediaAsset/MediaObservation.
- [ ] T02.13 Implement ContentRun/StepRun/Artifact/Approval.
- [ ] T02.14 Implement ContextManifest.
- [ ] T02.15 Implement ModelCall/ToolCall/QualityEvaluation.
- [ ] T02.16 Seed project `motgu`.
- [ ] T02.17 Seed `vi-VN` and `en` locale settings.
- [ ] T02.18 Add settings snapshot reproducibility tests.
- [ ] T02.19 Add ContentCase → two LocaleVariant contract test.
- [ ] T02.20 Add ContentItem version lineage test.
- [ ] T02.21 Add versioned Research artifact/source-ref contract.
- [ ] T02.22 Add Opportunity Map artifact/version contract with locale + signal/source refs.
- [ ] T02.23 Add Knowledge Candidate status/provenance contract for later Obsidian mirror.

---

## CE03 — Durable Harness

- [ ] T03.1 Implement Run state machine.
- [ ] T03.2 Implement StepRun attempt lifecycle.
- [ ] T03.3 Implement durable job queue.
- [ ] T03.4 Implement atomic worker claim.
- [ ] T03.5 Implement worker lease/heartbeat.
- [ ] T03.6 Implement expired lease reclaim.
- [ ] T03.7 Implement checkpoints.
- [ ] T03.8 Implement approval pause/resume.
- [ ] T03.9 Implement artifact version invalidation of approval.
- [ ] T03.10 Implement error classification + bounded retry.
- [ ] T03.11 Implement per-run/per-step budget.
- [ ] T03.12 Implement ModelRouter interface.
- [ ] T03.13 Implement ToolAdapter interface.
- [ ] T03.14 Implement ContextManifest creation/use.
- [ ] T03.15 Implement ModelCall/ToolCall telemetry.
- [ ] T03.16 Implement durable outbox for side effects.
- [ ] T03.17 Implement reconciliation contract.
- [ ] T03.18 Implement restart/resume integration test.
- [ ] T03.19 Implement duplicate side-effect prevention test.
- [ ] T03.20 Implement replay/eval run mode.

---

## CE04 — Knowledge + Production Research

- [ ] T04.1 Source registry.
- [ ] T04.2 Canonicalize source into normalized text/Markdown.
- [ ] T04.3 Content fingerprint and deterministic chunk IDs.
- [ ] T04.4 Dedupe test.
- [ ] T04.5 Chunking with bounded size.
- [ ] T04.6 Entity linking baseline.
- [ ] T04.7 Retrieval interface.
- [ ] T04.8 Authority-aware ranking.
- [ ] T04.9 Production ResearchRouter with provider budget/fallback rules.
- [ ] T04.10 Production Serper discovery adapter.
- [ ] T04.11 Production Tavily source discovery adapter.
- [ ] T04.12 Production Exa semantic/second-hop adapter.
- [ ] T04.13 Production Jina selected-page reader.
- [ ] T04.14 Keep Brave optional; implement only if coverage/outage evidence justifies it.
- [ ] T04.15 Discovery Research workflow.
- [ ] T04.16 Opportunity Map workflow with Keyword/Question Map tool.
- [ ] T04.17 Source commercial-bias/type/authority metadata.
- [ ] T04.18 Evidence Research workflow.
- [ ] T04.19 Claim extraction workflow.
- [ ] T04.20 Evidence linking workflow.
- [ ] T04.21 Contradiction representation.
- [ ] T04.22 EvidenceSet lock/version.
- [ ] T04.23 OriginalityPack builder.
- [ ] T04.24 Knowledge Candidate extraction.
- [ ] T04.25 Candidate → approved admission flow.
- [ ] T04.26 Obsidian mirror/export for approved knowledge/topic/research notes.
- [ ] T04.27 Test raw SERP/API payload is not mirrored to Obsidian by default.
- [ ] T04.28 Memory gap/create-update-refresh recommendation.
- [ ] T04.29 Provenance end-to-end test.
- [ ] T04.30 Test Discovery signal cannot silently become factual evidence.
- [ ] T04.31 Test second-hop can trace a summary article to an original source candidate.

---

## CE05 — Journal Engine V1

- [ ] T05.1 ContentCase/LocaleVariant Journal UI.
- [ ] T05.2 Internal knowledge recall.
- [ ] T05.3 Content Memory overlap check stub.
- [ ] T05.4 Discovery Research step.
- [ ] T05.5 Opportunity Map selection handoff.
- [ ] T05.6 Evidence Research + EvidenceSet step.
- [ ] T05.7 OriginalityPack step.
- [ ] T05.8 Angle generator structured output.
- [ ] T05.9 Angle approval UI/state.
- [ ] T05.10 Outline with evidence mapping.
- [ ] T05.11 Draft writer `vi-VN`.
- [ ] T05.12 Draft writer `en` independent from Vietnamese.
- [ ] T05.13 Review/revise bounded loop.
- [ ] T05.14 Assertion Audit.
- [ ] T05.15 Basic source-copy check.
- [ ] T05.16 Final content package.
- [ ] T05.17 One real MOTGU Journal end-to-end candidate.

---

## CE06 — Full Quality + Golden Regression

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