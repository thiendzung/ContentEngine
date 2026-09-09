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

Status: **CLOSED / PASS / GO TO CE02**.

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

Status: **CLOSED / MERGED**.

PR: `#7`

Merge commit: `fd86b67d587fdab663915fac106f751f34551c59`

- [x] T01.31 Collect 3–5 approved positive MOTGU excerpts for first locale.
- [x] T01.32 Collect 3–5 approved negative examples for first locale.
- [x] T01.33 Define short human editorial review form.
- [x] T01.34 Define one MOTGU ContentCase from selected ContentOpportunity.
- [x] T01.35 Define one real LocaleVariant.
- [x] T01.36 Build selected/manual EvidenceSet from higher-quality sources, not default Google top 1–5.
- [x] T01.37 Build Manual OriginalityPack.

PR-D evidence: `docs/13-CE01-CONTENT-INPUT-PRICE.md` records 4 founder-approved positive English examples, 4 founder-approved negative examples, the human editorial review form, ContentCase `cc_ce01_price_001`, English LocaleVariant `lv_ce01_price_en_001`, locked EvidenceSet `es_ce01_price_v1`, and approved OriginalityPack `opack_ce01_price_v1`. Founder decision on `2026-09-06`: `APPROVE CALIBRATION + CONTENT DIRECTION`. The approved scope is limited to helping a first-time buyer understand/evaluate a displayed artwork price; it does not claim an exact MOTGU/artist pricing formula. NeedHypothesis remains `PROPOSED`.

### PR-E — Golden Journal Walking Skeleton

Status: **CLOSED / MERGED / PASS**.

PR: `#8 — CE01 PR-E — Golden Journal walking skeleton`

Merge commit: `b9b9d94c6052750215194db66f25003280489cbc`

- [x] T01.38 Implement/manual-drive Angle step.
- [x] T01.39 Implement/manual-drive Outline step.
- [x] T01.40 Implement Draft step through ModelRouter seam or temporary single adapter.
- [x] T01.41 Add basic assertion audit.
- [x] T01.42 Run human editorial review.
- [x] T01.43 Record research/content failure notes without auto-changing contract.
- [x] T01.44 Gate: decide whether Research + Opportunity Map + content contract is good enough for CE02.

PR-E evidence: Founder selected Angle A, approved Outline V2, and approved Journal V2 on `2026-09-06`. Runtime Artwork anchor `Tranh đường tàu phố cổ Hà Nội — Hoa Lê` was verified before Draft. Draft EN V2 is `docs/17-CE01-GOLDEN-JOURNAL-DRAFT-EN.md`; Assertion Audit V2 is `docs/18-CE01-GOLDEN-JOURNAL-ASSERTION-AUDIT.md` with zero critical unsupported assertions. Failure/improvement notes are preserved in `docs/logs/2026-09-06-ce01-improvement-loop.md` and final closeout in `docs/logs/2026-09-06-ce01-closeout.md`. T01.44 decision: `GO TO CE02`. NeedHypothesis remains `PROPOSED`.

### CE01 exit gate

- [x] Repo build/test clean.
- [x] One founder-proposed NeedHypothesis + real signals produces a readable Opportunity Map.
- [x] Human selects at least one opportunity with clear audience/problem/MOTGU advantage.
- [x] Selected research/evidence sources are demonstrably better than blindly taking Google top results.
- [x] One real Journal reaches human review.
- [x] Zero critical unsupported assertion in the reviewed candidate.

---

## CE02 — Core Data + Settings

- [x] T02.1 Implement Project.
- [x] Implement Signal, NeedHypothesis, ContentOpportunity and ContentExperiment contracts;
      do not create legacy ProblemDesire/AudienceSignal models. Update ContentCase refs.
- [x] T02.2 Implement ContentCase.
- [x] T02.3 Implement LocaleVariant.
- [x] T02.4 Implement ContentItem/ContentVersion.
- [x] T02.5 Implement SettingsVersion/SettingsSnapshot.
- [x] T02.6 Implement Prompt/Recipe Registry.
- [x] T02.7 Implement Brand DNA/Language DNA validation.
- [x] T02.8 Implement Calibration Example storage.
- [x] T02.9 Implement Source/SourceDocument/KnowledgeChunk.
- [x] T02.10 Implement Entity/Claim/Evidence/EvidenceSet.
- [x] T02.11 Implement OriginalityPack.
- [x] T02.12 Implement MediaAsset/MediaObservation.
- [x] T02.13 Implement ContentRun/StepRun/Artifact/Approval.
- [x] T02.14 Implement ContextManifest.
- [x] T02.15 Implement ModelCall/ToolCall/QualityEvaluation.
- [x] T02.16 Seed project `motgu`.
- [x] T02.17 Seed `vi-VN` and `en` locale settings.
- [x] T02.18 Add settings snapshot reproducibility tests.
- [x] T02.19 Add ContentCase → two LocaleVariant contract test.
- [x] T02.20 Add ContentItem version lineage test.
- [x] T02.21 Add versioned Research artifact/source-ref contract.
- [x] T02.22 Add Opportunity Map artifact/version contract with locale + signal/source refs.
- [x] T02.23 Add Knowledge Candidate status/provenance contract for later Obsidian mirror.

---

## CE03 — Durable Harness

Status: **CLOSED / PASS**.

- PR-A = CLOSED / MERGED / PASS.
- PR-B = CLOSED / MERGED / PASS.
- PR-C = CLOSED / MERGED / PASS.
- PR-D = CLOSED / MERGED / PASS.
- PR-E = CLOSED / MERGED / PASS.

- [x] T03.1 Implement Run state machine.
- [x] T03.2 Implement StepRun attempt lifecycle.
- [x] T03.3 Implement durable job queue.
- [x] T03.4 Implement atomic worker claim.
- [x] T03.5 Implement worker lease/heartbeat.
- [x] T03.6 Implement expired lease reclaim.
- [x] T03.7 Implement checkpoints.
- [x] T03.8 Implement approval pause/resume.
- [x] T03.9 Implement artifact version invalidation of approval.
- [x] T03.10 Implement error classification + bounded retry.
- [x] T03.11 Implement per-run/per-step budget.
- [x] T03.12 Implement ModelRouter interface.
- [x] T03.13 Implement ToolAdapter interface.
- [x] T03.14 Implement ContextManifest creation/use.
- [x] T03.15 Implement ModelCall/ToolCall telemetry.
- [x] T03.16 Implement durable outbox for side effects.
- [x] T03.17 Implement reconciliation contract.
- [x] T03.18 Implement restart/resume integration test.
- [x] T03.19 Implement duplicate side-effect prevention test.
- [x] T03.20 Implement replay/eval run mode.

---

## CE04 — Knowledge + Production Research

- Status: **ACTIVE**.

- PR-A = CLOSED / MERGED / PASS.
- PR-B = CLOSED / MERGED / PASS.
- PR-C = CLOSED / MERGED / PASS.
- PR-D = CLOSED / MERGED / PASS.
- PR #26 merge commit = `46af24d6c17df483fdc32721f14bc2f9156d0d76`.
- PR-E = CLOSED / MERGED / PASS.
- PR #28 merge commit = `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.
- PR-F = ACTIVE / READY FOR REVIEW.
- Current PR = `CE04 PR-F — Knowledge Admission + Provenance Gates` (READY FOR REVIEW).
- Current implementation slice = `T04.35; final regression complete; merge pending user`.

PR-D post-merge closeout record:

- Merged branch: `ce04-discovery-opportunity-handoff`.
- Closeout branch: `ops-ce04-pr-d-closeout`.
- Base main: `46af24d6c17df483fdc32721f14bc2f9156d0d76`.
- PR #26: CLOSED / MERGED / PASS.
- Merge commit: `46af24d6c17df483fdc32721f14bc2f9156d0d76`.
- Evidence: `docs/logs/2026-09-07-ce04-pr-d-start.md`, `docs/logs/2026-09-07-ce04-pr-d-architecture-decision.md`, `docs/logs/2026-09-07-ce04-pr-d-real-gate.md`, `docs/logs/2026-09-07-ce04-pr-d-founder-selection.md`, `docs/logs/2026-09-07-ce04-pr-d-selection-gate.md`.
- Real Discovery Gate = PASS; founder selection = O4 / `opp_4c397247e40db8ae`; HumanSelection persistence = PASS; ContentExperiment draft persistence = PASS; idempotency = PASS; providers called during selection = 0; NeedHypothesis = `PROPOSED`; ContentCase and ContentRun counts unchanged.
- T04.1–T04.17 = DONE.
- T04.18–T04.23 = DONE.
- T04.24–T04.35 = NOT STARTED.

PR-E post-merge closeout record:

- Branch: `ce04-evidence-research-evidence-set`.
- PR #28: CLOSED / MERGED / PASS.
- Merge commit: `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.
- Closeout log: `docs/logs/2026-09-08-ce04-pr-e-closeout.md`.
- T04.18–T04.23 = DONE; final review, CI and post-merge verification passed.
- EvidenceSet v8 remains locked and OriginalityPack remains unchanged.
- NeedHypothesis `530bdd27-f008-4910-9b3b-df83e007cfa2` remains `PROPOSED`; ContentExperiment remains `PLANNED / PENDING`.

- [x] T04.1 Source registry.
- [x] T04.2 Canonicalize source into normalized text/Markdown.
- [x] T04.3 Content fingerprint and deterministic chunk IDs.
- [x] T04.4 Dedupe test.
- [x] T04.5 Chunking with bounded size.
- [x] T04.6 Entity linking baseline.
- [x] T04.7 Retrieval interface.
- [x] T04.8 Authority-aware ranking.
- [x] T04.9 Production ResearchRouter with provider budget/fallback rules.
- [x] T04.10 Production Serper discovery adapter.
- [x] T04.11 Production Tavily source discovery adapter.
- [x] T04.12 Production Exa semantic/second-hop adapter.
- [x] T04.13 Production Jina selected-page reader.
- [x] T04.14 Keep Brave optional; implement only if coverage/outage evidence justifies it.
- T04.14 PASS decision: **DO NOT IMPLEMENT BRAVE IN PR-C**; real runs did not prove a concrete coverage/outage need.
- [x] T04.15 Discovery Research workflow.
- [x] T04.16 Opportunity Map workflow with Keyword/Question Map tool.
- [x] T04.17 Source commercial-bias/type/authority metadata.
- [x] T04.18 Evidence Research workflow.
- [x] T04.19 Claim extraction workflow.
- [x] T04.20 Evidence linking workflow.
- [x] T04.21 Contradiction representation.
- [x] T04.22 EvidenceSet lock/version.
- [x] T04.23 OriginalityPack builder.
- [x] T04.24 Knowledge Candidate extraction.
- [x] T04.25 Candidate → approved admission flow.
- [x] T04.26 Obsidian mirror/export for approved knowledge/topic/research notes.
- [x] T04.27 Test raw SERP/API payload is not mirrored to Obsidian by default.
- [x] T04.28 Memory gap/create-update-refresh recommendation.
- [x] T04.29 Provenance end-to-end test.
- [x] T04.30 Test Discovery signal cannot silently become factual evidence.
- [x] T04.31 Test second-hop can trace a summary article to an original source candidate.
- [x] T04.32 EvidenceSet approval binds exact ID + version + hash.
- [x] T04.33 Lock rejects missing/stale/wrong approval.
- [x] T04.34 Isolated test database.
- [x] T04.35 CE04 final regression + closeout.

PR-F activation record:

- Branch: `ce04-knowledge-admission-provenance`.
- Base main: `85636cb4c562d4dd1ea37bff507dd75ea89bc201`.
- Start log: `docs/logs/2026-09-08-ce04-pr-f-start.md`.
- Scope: T04.24–T04.35; activation is docs-only and implementation is not started.
- F1: T04.24–T04.25 — Knowledge Candidate + human approval.
- F2: T04.26–T04.28 — Obsidian + raw-data guard + memory gap.
- F3: T04.29–T04.31 — Provenance + Discovery/Evidence + second-hop.
- F4: T04.32–T04.35 — Approval enforcement + isolated DB + final gate.
- Invariants at activation: EvidenceSet v8 and OriginalityPack unchanged; NeedHypothesis remains `PROPOSED`; ContentExperiment remains `PLANNED / PENDING`; O4 ContentCase ContentRun count = `0`; global ContentRun count is environment-dependent; KnowledgeCandidate = `0`; provider calls = `0`.
- Do not implement T04.24, mutate DB, call providers, tick T04.24+, or merge in activation.

PR-F T04.24 closeout record:

- Real extraction produced exactly four KnowledgeCandidate rows from locked EvidenceSet v8; the identical command was run a second time and reused the same four IDs.
- T04.24 = DONE after MG CONTENT ENGINE candidate review record.
- MG proposed for T04.25 admission: `08693242-d5c5-51b2-bde9-141c2933417d` (direct MCI price-context statement) and `1c9d6c34-91fe-5da2-af33-08a4dc39e2e2` (IRS valuation discussion factors and market context).
- MG proposed not for T04.25 admission: `212f0c96-cb30-50ea-8759-8912580d0981` (appraiser qualifications are not direct buyer price guidance) and `da9a7cf5-9a74-522c-9ee9-52a1198aa194` (panel FMV review process is not direct buyer price guidance).
- This closeout records review decisions only. Candidate rows were not mutated; status remains `CANDIDATE`, reviewer and review_reason remain null.
- Provider calls = `0`; EvidenceSet v8 and OriginalityPack were not changed.
- T04.25 = NOT STARTED. Next action: implement the admission gate using the recorded MG decision.

Closeout log: `docs/logs/2026-09-08-ce04-t04-24-candidate-review.md`.

PR-F T04.25 admission closeout record:

- T04.25 = DONE after applying the exact MG CONTENT ENGINE decisions to all four real O4 KnowledgeCandidates.
- Approved: `08693242-d5c5-51b2-bde9-141c2933417d`, `1c9d6c34-91fe-5da2-af33-08a4dc39e2e2`.
- Rejected: `212f0c96-cb30-50ea-8759-8912580d0981`, `da9a7cf5-9a74-522c-9ee9-52a1198aa194`.
- Each command was run twice with the exact expected hash, reviewer and reason; the second pass was terminal-idempotent with no duplicate rows.
- KnowledgeCandidate total = `4`; `APPROVED=2`; `REJECTED=2`; these four are no longer `CANDIDATE`; reviewer = `MG CONTENT ENGINE` and reasons match the exact MG record.
- Hash and locked EvidenceSet lineage verification passed for all four. EvidenceSet v8 and OriginalityPack were unchanged.
- ContentRun, Artifact and generic Approval deltas = `0`; provider calls = `0`.
- T04.26–T04.35 = NOT STARTED. No Obsidian export was performed.

Closeout log: `docs/logs/2026-09-08-ce04-t04-25-admission.md`.

PR-F T04.26 Obsidian mirror closeout record:

- T04.26 = DONE after the real mirror gate for the two approved O4 KnowledgeCandidates.
- Explicit temporary vault: `/tmp/motgu-ce04-obsidian-gate`; exactly two Markdown files were exported.
- `08693242-d5c5-51b2-bde9-141c2933417d.md` SHA-256 = `d93ee29a88b69be0a526285643b6de423fc1c0fae848cb5e743bb488b9051344`.
- `1c9d6c34-91fe-5da2-af33-08a4dc39e2e2.md` SHA-256 = `40f14af25b41be3494721457c374a7614c71de36d300539dc037152c5d316471`.
- The second export was byte-identical with the same paths and hashes.
- Rejected candidates `212f0c96-cb30-50ea-8759-8912580d0981` and `da9a7cf5-9a74-522c-9ee9-52a1198aa194` were both blocked with `candidate_status_not_exportable`.
- No rejected candidate ID, raw payload, raw response, HTML or page body appeared in the vault.
- Database mutation delta = `0`; no ContentRun was deleted or modified; provider calls = `0`.
- Global ContentRun: `4 → 4` (environment-dependent); O4 ContentCase `9ec6133b-5f14-46d0-9866-e3b049e537b5`: `0 → 0`.
- The old fixed `ContentRun=2` invariant was stale; scoped verification is now canonical and the drift reinforces T04.34's isolated test database requirement.
- T04.27–T04.35 = NOT STARTED. Next action: T04.27 raw search/API data mirror regression.

Closeout log: `docs/logs/2026-09-08-ce04-t04-26-obsidian-mirror.md`.

PR-F T04.27 raw mirror guard closeout record:

- T04.27 = DONE after `backend/tests/test_obsidian_raw_payload_guard.py` passed the
  recursive raw-payload boundary tests.
- Production code changed = none; the existing extraction/admission/mirror validation
  was proven by regression tests.
- All eight forbidden keys were tested recursively: `body`, `html`, `payload`, `raw`,
  `raw_payload`, `raw_response`, `response`, and `result`.
- Safe `provider`, `query`, `source_url`, `source_ref`, Evidence and SourceDocument
  references remained traceable. Raw SourceDocument body remained audit-only.
- Sanitized approved knowledge mirrored cleanly. A tampered approved candidate was
  rejected before writing with `candidate_raw_provenance_rejected`.
- Candidate, EvidenceSet, OriginalityPack, scoped O4 ContentRun, Artifact and Approval
  deltas = `0`; provider calls = `0`.
- T04.24–T04.27 = DONE. T04.28–T04.35 = NOT STARTED. Next action: T04.28 memory
  gap/create-update-refresh recommendation.

Closeout log: `docs/logs/2026-09-08-ce04-t04-27-raw-mirror-guard.md`.

PR-C evidence: ResearchRouter checks internal knowledge first, then uses Serper for production discovery, Tavily as a real conditional fallback, Exa for real second-hop research with parent provenance, and Jina for selected-page reading with bounded reader failover. PR-C reuses CE03 budget and ToolCall telemetry, classifies provider failures safely, and accepted the final Standard Gate result `sufficient=false` with explicit `bounded_search_exhausted` without weakening the sufficiency threshold. Secret scan passed. Brave was not implemented by the evidence-backed decision above. PR #24 merged with commit `39731375a5a90f3a6e590ed3c856d973d5feb1b9`. Final gate evidence: `docs/logs/2026-09-07-ce04-pr-c-final-gate.md`.
PR-F T04.28 memory gap closeout record:

- T04.28 = DONE after the exact real O4 CLI was run twice without `--refresh-before`.
- O4 opportunity `068991ab-de34-4787-9c38-8935c3f0e2da`: locale `en`, intent `evaluate`,
  stored decision `CREATE`, recommendation `CREATE`, `requires_human_review=false`,
  `planning_decision_mismatch=false`, and `unresolved_refs=[]`.
- No existing ContentItem target was found; no target was forced or selected. Refresh was
  not inferred: `refresh_before=null`, freshness basis `content_version_created_at`.
- Both serialized reports were identical. ContentItem, ContentVersion, ContentCase,
  scoped O4 ContentRun, Artifact, Approval and KnowledgeCandidate state were unchanged;
  EvidenceSet v8 and OriginalityPack were unchanged; provider calls = `0`.
- T04.24–T04.28 = DONE. T04.29–T04.35 = NOT STARTED. Next action: T04.29 provenance
  end-to-end test.

Closeout log: `docs/logs/2026-09-08-ce04-t04-28-memory-gap.md`.

PR-F T04.30 Discovery/evidence boundary closeout:

- T04.30 = DONE after a test-only boundary gate; no production code changed.
- Discovery persistence may create Signal, NeedHypothesisSignal and ContentOpportunitySignal
  planning rows, but Claim/Evidence/SourceDocument deltas remain `0`. A
  NeedHypothesisSignal `supports` relation is not factual Evidence.
- A Signal URL alone is rejected with `evidence_source_must_be_successfully_read`.
  Evidence Research with no successfully read document creates no Claim, Evidence or
  EvidenceSet and records that SEARCH snippets are ineligible for factual Evidence.
- The positive control persisted Source + SourceDocument and accepted only an exact
  excerpt present in the read document. Evidence resolved through SourceDocument to Source;
  Signal IDs were not factual lineage and `search_rank_used_as_authority=false`.
- Real O4 read-only audit found 6 Discovery signals linked to the opportunity and no direct
  Signal ID → Evidence relationship. Provider calls and real O4 DB mutation were `0`.
- Isolated backend gate: `275 passed, 1 skipped`; the skip is explicit because the isolated
  database has no real O4 fixture. Frontend and migration gates passed.
- T04.1–T04.30 = DONE. T04.31–T04.35 = NOT STARTED. Next action: T04.31 second-hop
  original-source trace.

Closeout log: `docs/logs/2026-09-08-ce04-t04-30-discovery-evidence-boundary.md`.

PR-F T04.31 second-hop provenance closeout:

- T04.31 = DONE after a bounded synthetic end-to-end gate; real providers and real O4
  records were not touched.
- Exact `parent_url` was preserved from the `ProductionResearchRequest` to the Exa
  second-hop candidate. The original candidate retained `relation=second_hop`,
  `parent_url`, `found_via=exa_second_hop`, `intended_use=evidence_candidate`,
  `source_type=institutional` and low commercial bias.
- When summary/direct and original candidates coexisted, the original second-hop URL was
  selected and read. Persisted Source and SourceDocument used the original URL; Source
  provenance retained the summary parent. Claim/Evidence accepted only an exact excerpt
  from the original SourceDocument, never summary text.
- Duplicate original URLs retained the stronger second-hop provenance. Missing or wrong
  parent provenance failed explicitly; unavailable Exa returned `exa_required_for_second_hop`
  without promoting a direct result.
- Focused result: `8 passed`. Full isolated backend, ruff, mypy and OpenAPI gates passed;
  migration round-trip and frontend gates passed. Provider calls = `0`; real O4 DB
  mutation = `0`.
- T04.1–T04.31 = DONE. T04.32–T04.35 = NOT STARTED. Next action: T04.32 EvidenceSet
  approval exact ID + version + hash.

Closeout log: `docs/logs/2026-09-08-ce04-t04-31-second-hop-provenance.md`.

PR-F T04.32 EvidenceSet approval closeout:

- T04.32 = DONE. Dedicated `EvidenceSetApproval` rows bind exact EvidenceSet ID, version
  and content hash before lock; harness `Approval` is not used.
- The service accepts draft non-empty EvidenceSets only, locks the row while validating,
  recomputes the stored hash from persisted Evidence IDs, and rejects version/hash drift.
  Exact same reviewer/reason repeats reuse the same immutable row; conflicting repeats fail.
- PostgreSQL blocks raw UPDATE and DELETE with `evidence_set_approval_is_immutable`.
- Migration `20260908_0011_evidence_set_approval` round-tripped on an isolated database.
  Focused tests: `7 passed`; isolated backend gate: `289 passed, 2 skipped`.
- Provider/model calls = `0`; real O4 DB mutation = `0`; EvidenceSet v8 remains locked and
  unchanged with no retrofit approval; OriginalityPack is unchanged.
- T04.1–T04.32 = DONE. T04.33–T04.35 = NOT STARTED. Next action: T04.33 lock enforcement.

Closeout log: `docs/logs/2026-09-08-ce04-t04-32-evidence-set-approval.md`.

PR-F T04.33 EvidenceSet lock approval closeout:

- T04.33 = DONE. New `draft → locked` transitions require a dedicated exact
  `EvidenceSetApproval` matching set ID, version and content hash. The service recomputes
  the hash from current Evidence IDs and does not trust the stored value alone.
- Missing, wrong-set, wrong-version, wrong-hash, nonexistent and corrupt approvals are
  rejected. Exact approval locks successfully without mutating the approval row.
- Database trigger `evidence_set_lock_requires_exact_approval` prevents raw SQL bypass;
  an approved draft snapshot cannot change its version, IDs, hash, project or content case.
- Evidence Research requests that ask to lock now require both `locked_by` and
  `evidence_set_approval_id`; normal research can still produce a draft EvidenceSet.
- The canonical `app.modules.knowledge.persistence.evidence_set_hash` is now used by
  EvidenceSet create/reuse and lock verification.
- Historical locked EvidenceSets remain idempotent without retrofit approval. EvidenceSet
  v8 and all O4 state remain unchanged; provider/model calls = `0`.
- Focused result: `21 passed, 1 skipped`; full isolated backend: `297 passed, 3 skipped`;
  migration upgrade → downgrade → upgrade: PASS. T04.1–T04.33 = DONE.
- T04.34–T04.35 = NOT STARTED. Next action: T04.34 isolated dedicated test database.

Closeout log: `docs/logs/2026-09-08-ce04-t04-33-lock-approval-gate.md`.

T04.33 direct-lock INSERT repair:

- Migration `20260908_0013_evidence_set_initial_draft_guard` rejects raw SQL and ORM
  insertion of `status=locked`, or draft rows with non-null `locked_at`/`locked_by`.
- Normal clean draft insertion and draft → exact approval → locked both pass. The guard
  applies only to future INSERTs; historical EvidenceSet v8 remains locked and unchanged,
  with no retrofit approval.
- Focused lock/approval and dependent workflow tests: `92 passed, 1 skipped`; full isolated
  backend gate: `297 passed, 3 skipped`. Migration upgrade → downgrade → upgrade, Ruff,
  mypy, OpenAPI and frontend gates pass; generic Approval, ContentRun and Artifact deltas
  are `0`; provider/model calls = `0`.
- T04.33 remains `DONE`; T04.34–T04.35 remain `NOT STARTED`.

PR-F T04.34 isolated test database closeout:

- T04.34 = `DONE`. Automated tests now require `APP_ENV=test` with a dedicated
  `TEST_DATABASE_URL`; the resolved URL is shared by the application engine, sessions and
  Alembic. Test engines use `NullPool`, and the test database target must contain `test` and
  differ from the application target.
- Dedicated local test database: `contentengine_t0434_test`. Normal application database:
  `contentengine`. The normal database was read-only before and after the gate with the same
  observed counts: projects `1`, ContentRun `4`, EvidenceSet `8`, KnowledgeCandidate `4`,
  Source `15`, SourceDocument `15`; O4 ContentRun remained `0`.
- Full isolated backend run 1: `304 passed, 0 skipped`. Full isolated backend run 2 after
  migration round-trip: `304 passed, 0 skipped`. Ruff, mypy, OpenAPI and frontend
  lint/typecheck/build passed.
- Migration `upgrade → downgrade 20260902_0001 → upgrade` passed on the dedicated database.
  The three real-O4 automated skips were removed; those production-fixture audits now live
  in `backend/scripts/audit_real_o4_readonly.py` and remain explicitly read-only.
- Provider/model calls = `0`; normal local DB mutation = `0`; O4 EvidenceSet v8,
  NeedHypothesis, OriginalityPack and scoped ContentRun remained unchanged. T04.35 remains
  `NOT STARTED`; next action is the CE04 final regression and closeout gate.

PR-F T04.35 final regression pre-merge closeout:

- T04.35 = `DONE` after the final regression on dedicated test database
  `contentengine_t0434_test`. Full backend after migration round-trip: run 1 `304 passed,
  0 skipped`; run 2 `304 passed, 0 skipped`. Migration upgrade → downgrade `20260902_0001`
  → upgrade returned to `20260908_0013 (head)`. Ruff, mypy, OpenAPI and frontend
  lint/typecheck/build passed.
- Read-only O4 audit traced both APPROVED candidates through locked EvidenceSet v8, Claim,
  Evidence, SourceDocument and Source. MCI and IRS canonical URLs matched persisted rows;
  recomputed hashes and excerpt checks passed. Six Discovery signals remain planning context
  with no direct Signal → Evidence lineage.
- EvidenceSet v8 remains locked with `0` historical approval rows (the normal application DB
  is at `20260906_0010`, before the approval table; no retrofit was performed). OriginalityPack
  `6bd287ec-43f9-4d69-957c-2223f258f909` remains draft with 4 structured/usable items.
  KnowledgeCandidate total remains `4` (`APPROVED=2`, `REJECTED=2`, `CANDIDATE=0`).
- Normal application DB counts and O4 scoped ContentRun remained unchanged; provider,
  Search and URL calls = `0`. Exit gates A–H and PR-F hardening checks are `PASS`.

Pre-merge handoff:

```text
CE04 IMPLEMENTATION: COMPLETE
T04: 1–35 DONE
PR: #29
MERGE: PENDING USER
POST-MERGE VERIFY: PENDING
CE05: DO NOT START
```

PR-C evidence: ResearchRouter checks internal knowledge first, then uses Serper for production discovery, Tavily as a real conditional fallback, Exa for real second-hop research with parent provenance, and Jina for selected-page reading with bounded reader failover. PR-C reuses CE03 budget and ToolCall telemetry, classifies provider failures safely, and accepted the final Standard Gate result `sufficient=false` with explicit `bounded_search_exhausted` without weakening the sufficiency threshold. Secret scan passed. Brave was not implemented by the evidence-backed decision above. PR #24 merged with commit `39731375a5a90f3a6e590ed3c856d973d5feb1b9`. Final gate evidence: `docs/logs/2026-09-07-ce04-pr-c-final-gate.md`.

PR-D evidence: implementation tests, real Discovery Gate, founder O4 selection, persistence and idempotency verification all passed. PR #26 merged with commit `46af24d6c17df483fdc32721f14bc2f9156d0d76`. NeedHypothesis remains `PROPOSED`; no ContentCase or ContentRun was created. See the five PR-D evidence logs listed in the post-merge closeout record above.

PR-E closeout evidence: `docs/logs/2026-09-08-ce04-pr-e-closeout.md` records the final
human-reviewed Evidence Gate, locked EvidenceSet v8, persisted Founder-approved
OriginalityPack, focused CE04 tests and the final isolated CI gate. T04.18–T04.23 are
DONE. NeedHypothesis remains `PROPOSED`, ContentExperiment remains `PLANNED / PENDING`,
ContentRun remains `2`, KnowledgeCandidate remains `0`, and T04.24–T04.35 remain NOT
STARTED. PR #28 is CLOSED / MERGED / PASS; current active slice is PR-F.

### CE04 final documentation closeout

CE04 STATUS: `CLOSED / PASS`

T04.1–T04.35: `DONE`

PR #29: `MERGED`

Merge commit: `e6f7ac185094d7898cfb8df3c26b38f8fc4f4718`

Post-merge CI #430: `PASS`

Post-merge verify: `PASS`

Branch cleanup: `DONE`

Next phase: `CE05 — Journal Engine V1`

CE05: `ACTIVE / PR-B.1`

---

## CE05 — Journal Engine V1

- Current PR: `CE05 PR-B.1 — Research Handoff + Evidence Gates`.
- Branch: `ce05-research-angle-outline`.
- Scope: `T05.4–T05.7`.
- [x] T05.1 ContentCase/LocaleVariant Journal UI.
- [x] T05.2 Internal knowledge recall.
- [x] T05.3 Content Memory overlap check stub.
- [x] T05.4 Discovery Research step.
- [x] T05.5 Opportunity Map selection handoff.
- [x] T05.6 Evidence Research + EvidenceSet step.
- [x] T05.7 OriginalityPack step.
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
- [ ] T05.18 Critical Gate Regression.
- [ ] T05.19 Resume / Replay Gate.
- [ ] T05.20 Human Review Surface.
- [ ] T05.21 CE05 Metrics Baseline.
- [ ] T05.22 CE05 Closeout.

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
