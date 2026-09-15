# K3 main retarget sync

Date: 2026-09-15

PR #96 has been retargeted from the historical `knowledge/k2-freshness` stack base to `main` after merged PR #95.

Integrated base: `main` at merge commit `14bbdca76c5b8c389834e1cf2bd38dae9a79a014`.

This file is evidence-only. It changes no K3 runtime, schema, provenance or freshness semantics. Its purpose is to force a fresh exact-head CI run against the integrated main lineage before PR #96 can be marked Ready for Review.

Required gate before Ready:

- PR remains mergeable against current `main`;
- diff contains only K3 implementation/tests/migration plus documentation evidence;
- fresh CI passes backend lint/types/migration/tests/OpenAPI and frontend generation/lint/typecheck/build;
- no operational DB migration or external provider/model execution is performed.
