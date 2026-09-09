# CE05 PR-B.1 hardening

Date: 2026-09-09

Start HEAD: `d745caa915235cf6353fad13deb9ced9bede6207`

## Scope

- Harden exact EvidenceSet handoff lineage.
- Add durable OriginalityPack approval metadata and snapshot binding.
- Persist an immutable, canonical-hash `journal_input_bundle` Artifact.
- Keep research decisions bounded to `REUSE_EXISTING`, `RESEARCH_REQUIRED`, or `BLOCKED`.

## Locked decisions

- A locked historical EvidenceSet without a retrofit approval remains valid when its ID,
  project, ContentCase, version, content hash, and recomputed evidence-ID hash match.
- If EvidenceSet approval rows exist, every row must match the exact locked snapshot.
- Journal handoff accepts only an approved OriginalityPack with non-empty reviewer/reason,
  exact snapshot hash, and usable MOTGU-owned material. Draft and retired packs block.
- Approved OriginalityPack content and approval metadata are database-guarded as immutable;
  approved → retired is the only lifecycle transition retained.
- `journal_input_bundle` stores the selected Opportunity payload, exact EvidenceSet and
  OriginalityPack refs, decision, and provider/model call counts. Repeating the same input
  within a run reuses the same Artifact and hash.

## Safety

No real O4 OriginalityPack was approved or mutated. No provider call, model call, Angle,
draft, T05.8+ work, or merge was performed.

## Local evidence

- Focused CE05 handoff tests: `13 passed`.
- Full backend: `326 passed`.
- Ruff and mypy: passed.
- Migration round-trip: `upgrade → downgrade 20260902_0001 → upgrade`, ending at
  `20260909_0015`.
- OpenAPI generation and frontend lint/typecheck/build: passed.
- GitHub Actions CI: run `34327816627` / PASS.
