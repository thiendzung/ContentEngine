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

### T00.14 xác nhận

- [x] ContentCase/LocaleVariant thống nhất ở mọi spec.
- [x] ContentItem/ContentVersion thống nhất ở mọi spec.
- [x] EvidenceSet/ContextManifest/ContentAssertion không còn reference mồ côi.
- [x] Discovery Research và Evidence Research được tách rõ.
- [x] Media Evidence khớp Artwork/Data/Quality.
- [x] Worker lease/outbox/reconciliation khớp Architecture/Harness/Plan.
- [x] Quality tối thiểu có trước Journal production.
- [x] Walking Skeleton nằm trong CE01.
- [x] Settings source of truth chỉ có một.
- [x] AGENTS Contract Change Mode khớp governance.

---

## CE01 — Repository Skeleton + Walking Skeleton

### Repository

- [ ] T01.1 Create branch `ce01-walking-skeleton` from clean main.
- [ ] T01.2 Create backend FastAPI package.
- [ ] T01.3 Create frontend Next.js shell tối thiểu.
- [ ] T01.4 Add root developer scripts.
- [ ] T01.5 Add `.env.example`, never secrets.
- [ ] T01.6 Add PostgreSQL connection + migration framework.
- [ ] T01.7 Add module directories matching Architecture Spec.
- [ ] T01.8 Add health/version endpoint.
- [ ] T01.9 Add backend lint/type/test baseline.
- [ ] T01.10 Add frontend lint/type/build baseline.
- [ ] T01.11 Add OpenAPI generation + generated frontend types.
- [ ] T01.12 Add CI required checks.
- [ ] T01.13 Verify clean install from fresh checkout.

### Editorial calibration

- [ ] T01.14 Collect 3–5 approved positive MOTGU excerpts for first locale.
- [ ] T01.15 Collect 3–5 approved negative examples for first locale.
- [ ] T01.16 Define short human editorial review form.
- [ ] T01.17 Define one real MOTGU ContentCase.
- [ ] T01.18 Define one real LocaleVariant.
- [ ] T01.19 Build Manual EvidenceSet.
- [ ] T01.20 Build Manual OriginalityPack.

### Walking Skeleton

- [ ] T01.21 Implement/manual-drive Angle step.
- [ ] T01.22 Implement/manual-drive Outline step.
- [ ] T01.23 Implement Draft step through ModelRouter seam or temporary single adapter.
- [ ] T01.24 Add basic assertion audit.
- [ ] T01.25 Run human editorial review.
- [ ] T01.26 Record failure/learning notes without auto-changing contract.
- [ ] T01.27 Gate: decide whether content contract is good enough for CE02.

---

## CE02 — Core Data + Settings

- [ ] T02.1 Implement Project.
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

## CE04 — Knowledge + Discovery + Evidence

- [ ] T04.1 Source registry.
- [ ] T04.2 Canonicalize source into normalized text/Markdown.
- [ ] T04.3 Content fingerprint and deterministic chunk IDs.
- [ ] T04.4 Dedupe test.
- [ ] T04.5 Chunking with bounded size.
- [ ] T04.6 Entity linking baseline.
- [ ] T04.7 Retrieval interface.
- [ ] T04.8 Authority-aware ranking.
- [ ] T04.9 Discovery Research workflow.
- [ ] T04.10 Evidence Research workflow.
- [ ] T04.11 Claim extraction workflow.
- [ ] T04.12 Evidence linking workflow.
- [ ] T04.13 Contradiction representation.
- [ ] T04.14 EvidenceSet lock/version.
- [ ] T04.15 OriginalityPack builder.
- [ ] T04.16 Memory gap/create-update-refresh recommendation.
- [ ] T04.17 Provenance end-to-end test.
- [ ] T04.18 Test Discovery signal cannot silently become factual evidence.

---

## CE05 — Journal Engine V1

- [ ] T05.1 ContentCase/LocaleVariant Journal UI.
- [ ] T05.2 Internal knowledge recall.
- [ ] T05.3 Content Memory overlap check stub.
- [ ] T05.4 Discovery Research step.
- [ ] T05.5 Evidence Research + EvidenceSet step.
- [ ] T05.6 OriginalityPack step.
- [ ] T05.7 Angle generator structured output.
- [ ] T05.8 Angle approval UI/state.
- [ ] T05.9 Outline with evidence mapping.
- [ ] T05.10 Draft writer `vi-VN`.
- [ ] T05.11 Draft writer `en` independent from Vietnamese.
- [ ] T05.12 Review/revise bounded loop.
- [ ] T05.13 Assertion Audit.
- [ ] T05.14 Basic source-copy check.
- [ ] T05.15 Final content package.
- [ ] T05.16 One real MOTGU Journal end-to-end candidate.

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

---

## CE09 — Content Memory + Learning

- [ ] T09.1 Published ContentItem/Version memory index.
- [ ] T09.2 Duplicate/intent overlap detector.
- [ ] T09.3 Create/update/refresh/merge/do-not-write recommendation.
- [ ] T09.4 Human edit delta classifier.
- [ ] T09.5 AudienceSignal model/service.
- [ ] T09.6 LearningCandidate lifecycle.
- [ ] T09.7 Minimum-evidence/sufficiency rules.
- [ ] T09.8 Approved learning change workflow.
- [ ] T09.9 Regression-before-promotion enforcement.
- [ ] T09.10 Month 1 review report.
- [ ] T09.11 Month 3 review report.
- [ ] T09.12 Month 6 audience narrowing report.

---

## CE10 — Pilot

- [ ] T10.1 Define 10–20 content hypotheses.
- [ ] T10.2 Balance pillar/cluster and Journal/Artwork.
- [ ] T10.3 Run production pilot.
- [ ] T10.4 Review quality failures.
- [ ] T10.5 Review human editing burden.
- [ ] T10.6 Review cost/latency.
- [ ] T10.7 Promote first stable Golden Set.
- [ ] T10.8 Review audience signals and evidence strength.
- [ ] T10.9 Decide next roadmap only from pilot evidence.
