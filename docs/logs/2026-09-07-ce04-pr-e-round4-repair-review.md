# CE04 PR-E — Round 4 Repair Review

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28

## Agent Local repair review

Agent Local repair commit:

`6a968b2e0e5dd7631f46439b6065ec1c1e0d0a5a`

Accepted:

- Evidence subject anchoring now uses `NeedHypothesis.statement`, not the Discovery planning label `Artsy prices`;
- `backend/scripts/curate_evidence_set.py` provides zero-provider, draft-only, idempotent EvidenceSet curation from exact reviewed Evidence IDs;
- relevant repair tests passed locally;
- GitHub CI #363 passed on the Agent Local repair head;
- local full-suite failures are not treated as a branch blocker because canonical GitHub CI passed the complete test gate in its isolated environment.

## MG follow-up finding

One authority loophole remained: non-`.com` brand domains such as `.org`, `.net`, `.io` could still auto-promote to `institutional` merely because the hostname contained words such as `museum`, `archive`, `association`, or `institute`.

This violates the conservative authority rule:

`provider/search relevance != authority`

and:

`domain naming words != authority proof`.

MG tightened automatic authority so only strong public/academic domain signals (`.gov` / `.edu`) auto-become institutional evidence candidates. All other unverified domains remain discovery/context candidates until human/source review.

Regression coverage was added for `.org`, `.net`, `.io`, `.edu`, and `.gov`.

CI #365 failed on exactly one legacy test that still asserted `examplemuseum.org = institutional`. The legacy assertion was updated to the new conservative contract; classifier was not weakened.

Current code head after the legacy-test fix:

`8a9a4e896d4db78e5af20127fc2b934fe95cd385`

Latest required CI: #366. Round 5 must not run until #366 is PASS.

## Evidence strategy decision

Do not curate Round 1–4 `supports` as production Evidence because their stored source metadata/relation may predate the final conservative authority contract.

Run one final bounded authority-targeted research pass instead.

Target source families:

- `irs.gov` — authoritative fair-market-value and art appraisal guidance;
- `si.edu` — Smithsonian guidance about artwork value, condition, market context, and professional appraisal.

After a successful authority-targeted run:

1. human-review exact Evidence rows;
2. select only approved Evidence IDs;
3. create a curated draft EvidenceSet with `provider_calls=0`;
4. review the curated draft;
5. lock that exact EvidenceSet separately with `provider_calls=0`.

Do not lock any auto-generated Round 1–4 EvidenceSet.

T04.18–T04.23 remain NOT DONE until the curated EvidenceSet and OriginalityPack gap are reviewed.