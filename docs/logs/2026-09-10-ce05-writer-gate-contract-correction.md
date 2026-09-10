# CE05 — Real bilingual Writer gate contract correction

Date: 2026-09-10
Decision owner: MG Content Engine under the canonical CE05 spec; Founder retains merge authority.

## Observed real runtime

Agent Local completed the real bilingual Writer runtime on main `e3c029f298269b9726ac89b2846b68b613d9eaf7` after the authorized `vi-VN` LocaleVariant repair.

Runtime/provenance results:

- exact `vi-VN` and `en` LocaleVariants existed before either Writer ran;
- migration `20260910_0019` and both locale registries verified;
- both Writers used `codex_cli / gpt-5.6-luna` through the immutable upstream route;
- VI and EN used separate `localize` ContentRuns and separate task keys;
- both bound the same accepted Outline, EvidenceSet, OriginalityPack and SettingsSnapshot;
- neither model input contained sibling draft/run input or translation input;
- support refs matched the accepted Outline exactly;
- ToolCalls remained zero;
- exact reruns reused the same run/handoff/draft with zero extra model calls;
- all upstream artifacts remained immutable.

Exact source drafts accepted as T05.13 inputs:

```text
vi-VN Writer run:
1f0b91a7-39d7-449f-84ad-988fd1e8f44e
Draft v1:
19c2c580-efb6-43ba-b1a9-0625f0804ede
Hash:
972093122732100b891651398677812942dcd759ed9f9e0a9122f92666cd0cc6
Declared unresolved factual claims: 0

en Writer run:
b2e86caf-a7a2-463a-8c8c-9e94e02272f5
Draft v1:
fdf54b59-92d3-4c42-ac14-e5a7ada26837
Hash:
cf1dbc56812dc6d0918b8accaf9d34c583a6719a6a2f86135e5e222069bdc495
Declared unresolved factual claims: 5
```

## Contract contradiction discovered

The T05.11/T05.12 Writer prompt intentionally instructs the model:

- if a useful new factual claim is unsupported by the bounded input, do not write it as fact;
- instead declare it in `unresolved_factual_claims`.

The first real gate task also required `unresolved_factual_claim_count = 0` before the draft could enter Review/Revise.

Those two rules conflict. A safety field designed to carry a declared gap into revision cannot also be prohibited at the Writer exit.

The canonical CE05 North Star is:

```text
approved outline
→ draft
→ assertion/source checks
→ bounded revision
→ final human approval
```

and CE05 PR-C explicitly covers independent VI/EN writers plus bounded revision.

## Decision

T05.11/T05.12 real Writer gate is **PASS** when all of the following hold:

1. real locale drafts exist with correct immutable lineage and provenance;
2. VI and EN are independent sibling generation paths;
3. exact Outline support refs are preserved;
4. no unsupported factual statement is invented;
5. any intended factual statement that cannot be supported is declared explicitly rather than silently written as fact;
6. retry/idempotency and upstream-immutability gates pass.

A non-zero `unresolved_factual_claim_count` is therefore allowed as an input to T05.13.

`unresolved_factual_claim_count = 0` becomes a mandatory **T05.13 exit gate** before T05.14 Assertion Audit.

## EN interpretation

The five EN entries from the real v1 draft are absence notes, not five unsupported facts asserted by the article. They state that artwork-specific identity/dimensions/material, practical costs, sale status/location, artwork-specific comparisons/context, and a specific fair-price determination were not supplied.

The EN prose did not invent those missing values. Therefore no new research or artwork-specific data is required to close T05.11/T05.12.

T05.13 must instead:

- preserve the safety boundary;
- remove or soften wording that would require missing facts;
- stop treating mere absence of non-asserted data as an unresolved factual claim;
- return zero unresolved items without fabricating the missing data.

## Editorial notes for bounded revision

These are polish targets, not new facts or new evidence:

- VI: prefer natural `giá niêm yết` or equivalent over awkward `giá trị được niêm yết` wording if encountered;
- EN: replace internal/technical phrasing such as `canonical listing` with natural reader-facing wording such as `current listing` or equivalent;
- EN: avoid unnecessary `investment value` phrasing;
- EN: improve the awkward closing sentence while preserving low-pressure posture.

## T05.13 invariants

- source draft v1 artifacts remain immutable;
- output is a new immutable `journal_draft` version in the same locale Writer run;
- exact section IDs/order and exact Evidence/Originality refs are preserved;
- no new research, Search, URL or ToolCall;
- no new Evidence/Originality refs;
- no specific current artwork/artist/commerce/market fact is invented;
- each locale is revised independently; no sibling draft input;
- final document-level and section-level `unresolved_factual_claims` arrays are all empty;
- exact rerun reuses the same revised artifact with zero additional model call.

## Non-goals

This decision does not:

- waive T05.14 Assertion Audit;
- claim the v1 drafts are publishable;
- add evidence or research;
- approve final content;
- change the Founder-selected Angle or accepted Outline;
- change any upstream artifact;
- start T05.14 before real T05.13 passes.
