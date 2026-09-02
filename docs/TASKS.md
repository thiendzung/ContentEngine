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
- [ ] T00.14 Final cross-document consistency review.

## CE01 — Repository Skeleton

- [ ] T01.1 Create branch `ce01-repo-skeleton` from clean main.
- [ ] T01.2 Create backend FastAPI package.
- [ ] T01.3 Create frontend Next.js package.
- [ ] T01.4 Add root developer scripts.
- [ ] T01.5 Add `.env.example`, never secrets.
- [ ] T01.6 Add DB connection and migration framework.
- [ ] T01.7 Add module directories matching Architecture Spec.
- [ ] T01.8 Add health/version endpoint.
- [ ] T01.9 Add frontend health shell.
- [ ] T01.10 Add backend lint/type/test baseline.
- [ ] T01.11 Add frontend lint/type/build baseline.
- [ ] T01.12 Add OpenAPI generation + generated frontend types.
- [ ] T01.13 Add CI required checks.
- [ ] T01.14 Verify clean install from fresh checkout.

## CE02 — Core Data + Settings

- [ ] T02.1 Implement Project model.
- [ ] T02.2 Implement SettingsVersion and SettingsSnapshot.
- [ ] T02.3 Implement Source/SourceDocument/KnowledgeChunk.
- [ ] T02.4 Implement Entity/Claim/Evidence.
- [ ] T02.5 Implement AudienceHypothesis/ProblemDesire.
- [ ] T02.6 Implement ContentBrief.
- [ ] T02.7 Implement ContentRun/StepRun/Artifact.
- [ ] T02.8 Implement Approval.
- [ ] T02.9 Implement ModelCall/QualityEvaluation.
- [ ] T02.10 Implement PublishedContent/PerformanceSnapshot.
- [ ] T02.11 Seed project `motgu`.
- [ ] T02.12 Seed `vi-VN` and `en` locale settings.
- [ ] T02.13 Add Brand DNA schema validation.
- [ ] T02.14 Add Language DNA schema validation.
- [ ] T02.15 Add versioned Writing Recipe schema.
- [ ] T02.16 Add settings snapshot reproducibility tests.

## CE03 — Durable Harness

- [ ] T03.1 Implement Run state machine.
- [ ] T03.2 Implement StepRun attempt lifecycle.
- [ ] T03.3 Implement durable checkpoint repository.
- [ ] T03.4 Implement approval pause/resume.
- [ ] T03.5 Implement artifact version invalidation of approval.
- [ ] T03.6 Implement error classification.
- [ ] T03.7 Implement bounded retry policy.
- [ ] T03.8 Implement per-run/per-step budget.
- [ ] T03.9 Implement ModelRouter interface.
- [ ] T03.10 Implement ToolAdapter interface.
- [ ] T03.11 Implement ModelCall/ToolCall telemetry.
- [ ] T03.12 Implement restart/resume integration test.
- [ ] T03.13 Implement duplicate side-effect protection.
- [ ] T03.14 Implement replay/eval run mode.

## CE04 — Knowledge + Evidence

- [ ] T04.1 Source registry.
- [ ] T04.2 Canonicalize source into normalized text/Markdown.
- [ ] T04.3 Content fingerprint and deterministic chunk IDs.
- [ ] T04.4 Dedupe test.
- [ ] T04.5 Chunking with bounded size.
- [ ] T04.6 Entity linking baseline.
- [ ] T04.7 Retrieval interface.
- [ ] T04.8 Authority-aware ranking.
- [ ] T04.9 Claim extraction workflow.
- [ ] T04.10 Evidence linking workflow.
- [ ] T04.11 Contradiction representation.
- [ ] T04.12 Evidence lock artifact.
- [ ] T04.13 Memory gap report.
- [ ] T04.14 Provenance end-to-end test.

## CE05 — Journal Engine V1

- [ ] T05.1 Journal Brief schema/UI.
- [ ] T05.2 Internal knowledge recall step.
- [ ] T05.3 Content Memory overlap check stub.
- [ ] T05.4 External research step.
- [ ] T05.5 Evidence lock step.
- [ ] T05.6 Angle generator structured output.
- [ ] T05.7 Angle approval UI/state.
- [ ] T05.8 Outline generator with evidence mapping.
- [ ] T05.9 Draft writer `vi-VN`.
- [ ] T05.10 Draft writer `en` independent from Vietnamese.
- [ ] T05.11 Review/revise bounded loop.
- [ ] T05.12 Final content package.
- [ ] T05.13 One real MOTGU Golden Journal candidate.

## CE06 — Quality + Golden Set

- [ ] T06.1 Evidence integrity evaluator.
- [ ] T06.2 Reader value evaluator.
- [ ] T06.3 Brand voice evaluator.
- [ ] T06.4 Originality evaluator.
- [ ] T06.5 Structure/readability evaluator.
- [ ] T06.6 Search/AI readability evaluator.
- [ ] T06.7 Language naturalness evaluator per locale.
- [ ] T06.8 Human review form.
- [ ] T06.9 Golden Set storage/versioning.
- [ ] T06.10 Weak/Failure Set storage.
- [ ] T06.11 Regression runner.
- [ ] T06.12 Candidate vs baseline report.

## CE07 — Artwork Engine V1

- [ ] T07.1 WordPress/WooCommerce canonical Artwork adapter.
- [ ] T07.2 Artwork fact lock.
- [ ] T07.3 Artist context retrieval.
- [ ] T07.4 Artwork visual/material observation contract.
- [ ] T07.5 Artist-intent provenance rule.
- [ ] T07.6 Artwork writer `vi-VN`.
- [ ] T07.7 Artwork writer `en`.
- [ ] T07.8 Related content linker.
- [ ] T07.9 Artwork quality gates.
- [ ] T07.10 One real MOTGU Golden Artwork candidate.

## CE08 — Publish + Measure

- [ ] T08.1 WordPress draft publish adapter.
- [ ] T08.2 Idempotency key and reconciliation.
- [ ] T08.3 Internal ↔ WordPress ID mapping.
- [ ] T08.4 Search Console adapter.
- [ ] T08.5 Analytics adapter.
- [ ] T08.6 MOTGU conversion-event mapping.
- [ ] T08.7 Rank Math signal feasibility spike.
- [ ] T08.8 PerformanceSnapshot import.
- [ ] T08.9 Content hypothesis → metrics traceability.

## CE09 — Memory + Learning

- [ ] T09.1 Published Content Memory index.
- [ ] T09.2 Duplicate/intent overlap detector.
- [ ] T09.3 Human edit delta classifier.
- [ ] T09.4 AudienceSignal model/service.
- [ ] T09.5 LearningCandidate lifecycle.
- [ ] T09.6 Approved learning change workflow.
- [ ] T09.7 Regression-before-promotion enforcement.
- [ ] T09.8 Month 1 review report.
- [ ] T09.9 Month 3 review report.
- [ ] T09.10 Month 6 audience narrowing report.

## CE10 — Pilot

- [ ] T10.1 Define 10–20 content hypotheses.
- [ ] T10.2 Balance pillar/cluster and Journal/Artwork.
- [ ] T10.3 Run production pilot.
- [ ] T10.4 Review quality failures.
- [ ] T10.5 Review human editing burden.
- [ ] T10.6 Review cost/latency.
- [ ] T10.7 Promote first stable Golden Set.
- [ ] T10.8 Decide next roadmap only from pilot evidence.
