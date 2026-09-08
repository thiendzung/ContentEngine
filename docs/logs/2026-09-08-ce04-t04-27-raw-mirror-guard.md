# CE04 T04.27 — Raw mirror guard closeout

Date: 2026-09-08
Branch: `ce04-knowledge-admission-provenance`
Start HEAD: `05048effd22cfb26ba12ef6375aff71f0f8f5153`
Scope: TEST + DOCS ONLY

## Goal

Prove that raw SERP/API/page payload cannot enter an approved Knowledge Obsidian
mirror by default.

## Evidence

- Test added: `backend/tests/test_obsidian_raw_payload_guard.py`.
- Production code changed: none.
- Recursive forbidden keys tested: `body`, `html`, `payload`, `raw`, `raw_payload`,
  `raw_response`, `response`, `result`.
- Sentinels tested: `RAW_SERP_SENTINEL_01`, `RAW_HTML_SENTINEL_02`,
  `RAW_PAGE_BODY_SENTINEL_03`, `RAW_PAYLOAD_SENTINEL_04`,
  `RAW_RESPONSE_SENTINEL_05`, `RAW_RESULT_SENTINEL_06`, `RAW_NESTED_SENTINEL_07`.
- Safe `provider`, `query`, `source_url`, `source_ref`, Evidence and SourceDocument
  references remained traceable in the sanitized candidate provenance.
- The raw/full SourceDocument body remained available for audit but was not mirrored.
- The sanitized approved candidate mirrored with the exact statement, source/evidence
  refs, reviewer and reason; no raw payload or page body appeared in Markdown.
- A tampered approved candidate was rejected before file creation with
  `candidate_raw_provenance_rejected`.
- Export was read-only for candidate, EvidenceSet, OriginalityPack, scoped O4 ContentRun,
  Artifact and Approval state.

## Gates

- Focused raw-guard and existing CE04 suites: `46 passed`.
- Isolated backend gate: `235 passed`; ruff, mypy and OpenAPI generation passed.
- Migration round-trip passed on the temporary isolated database.
- Frontend lint, typecheck and build passed.
- Provider calls: `0`.
- Database mutation: `0`.
- T04.24: DONE.
- T04.25: DONE.
- T04.26: DONE.
- T04.27: DONE.
- T04.28–T04.35: NOT STARTED.

Next action: T04.28 memory gap/create-update-refresh recommendation.
