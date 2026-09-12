# M1 Journal closeout — 2026-09-13

## Status

M1 ONE REAL JOURNAL PASS: **COMPLETE / MG ACCEPTED** on the Founder's local runtime.

Live merged repository ref at closeout review:

- `main == 8454e9fd3e2002901bea12c045826b1a5eac3b6d` (merge PR #76).
- Agent Local reported `HEAD == origin/main` and clean working tree for LF-04D.
- Migration head remained `20260912_0023`.

No publishing authority was granted or exercised.

## Durable bilingual closeout

ContentCase:

- `f0bfbad7-c266-4de1-8fd4-a85ad206e6ce`

### vi-VN

- LocaleVariant `e9fcf073-24a4-4231-98a5-e68ddbf1b5f6`
- final approved source draft `fa3fcfe8-3157-4dc5-9afe-8da21b13b576`, v3
- final hash `f72c0c87b3e599d6d0f1d919d5158c3968281fee0b10bfda577944872a78ee06`
- ContentItem `97fd2212-ea89-44a3-bfb8-ed612776d938`
- canonical key `journal:f0bfbad7-c266-4de1-8fd4-a85ad206e6ce:vi-VN`
- final_review StepRun `2855e4d4-2b1d-4545-9cec-34de6a75332f`, completed
- final_content Artifact `48a5f84b-2c52-402b-b1ac-14e4d6120f86`, v1, exact same hash as approved source draft
- Founder Approval `3956ae2f-3cd4-4923-8580-cc5bd81d3a1d`, decision `approved`
- ContentVersion `66ad367f-99af-4b37-8914-5b446fca50dd`, v1, status `approved`
- Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`, completed

### en

- LocaleVariant `c53a9c6c-08f0-4926-8e50-e3da6bd4a421`
- final approved source draft `43007d23-8fbf-498d-ac49-436414c87aaf`, v4
- final hash `f22d6875d8fbed4745555971496b669588f24762c5f083f5dbdad82c5d1cb205`
- ContentItem `c4d53c67-5e41-4420-86fb-9654e3fac70f`
- canonical key `journal:f0bfbad7-c266-4de1-8fd4-a85ad206e6ce:en`
- final_review StepRun `39bc9524-5bb2-4994-9f16-ffa7d27a7e3a`, completed
- final_content Artifact `c5dd7f40-56bf-406d-8442-d276ab9270fd`, v1, exact same hash as approved source draft
- Founder Approval `0a00f4a9-0b51-490f-a101-6da0c5489461`, decision `approved`
- ContentVersion `6dcc3b6a-a507-47fd-8461-e0f084427f2e`, v1, status `approved`
- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`, completed

Both ContentVersions bind exact `created_by_run_id` and `final_artifact_id`, and both final_content artifacts are byte-identical to the exact Founder-approved draft bytes.

## Founder final approval binding

The durable approval comments on both locales bind the exact:

- VI artifact/version/hash;
- EN artifact/version/hash;
- Operational Package JSON SHA-256 `9d804da5c8d0756930b577e8e4244408cf9a8236d7b9205a8135d215e61b429a`;
- Operational Package Markdown SHA-256 `a3804dd7622b9182c581b95aa2f892df2ee82a4e83c5c9a65f55ca802fa67c9f`;
- Founder acceptance of the two surviving non-critical EN Source-copy warnings;
- no content edits;
- no publish or WordPress authorization.

Exactly three mandatory human gates are now durably represented in the M1 lineage:

1. Angle approval;
2. Outline approval;
3. Founder final content approval.

## Quality state frozen at M1 closeout

VI:

- Assertion Audit v5 PASS, critical unsupported/contradicted `0/0`;
- Source-copy v2 PASS, `fail_count=0`, `warn_count=0`.

EN:

- Assertion Audit v5 PASS, critical unsupported/contradicted `0/0`;
- Source-copy v2 hard gate PASS, `fail_count=0`, `warn_count=2`.

Accepted EN warnings remain verbatim:

1. `section:condition-and-context:1` — overlap `by the same artist, and the state of the`; source `evidence_excerpt`; overlap tokens `9`.
2. `section:practical-costs:2` — overlap `oversize or special handling may require a quote`; source `originality_material`; overlap tokens `8`.

Do not reopen quality merely to remove these accepted warnings.

## Runtime mutation accounting

LF-04D reported:

- ContentRuns `11` unchanged;
- StepRuns `18 -> 20`;
- Artifacts `27 -> 33` (2 final_content artifacts + 4 approval checkpoints);
- ContentItems `0 -> 2`;
- ContentVersions `0 -> 2`;
- ModelCalls `14 -> 14`;
- ToolCalls `0 -> 0`;
- QualityEvaluations `7 -> 7`;
- published ContentVersions `0`.

No model/provider/tool/research/evaluator call occurred in LF-04D.

## No-publish boundary

At closeout:

- no PublishedContent;
- no PublishEvent;
- no URL mapping;
- no WordPress/external publishing action;
- `not_published=true` on the Operational Package;
- the frozen source Journal run remains `waiting_approval` by design and is not a closeout blocker.

M1 proves a real local Journal lineage through canonical approved bilingual ContentVersions. It does **not** claim publication, placement, traffic, or performance learning.

## Observed operational friction to retain

M1 surfaced concrete failure modes that must guide post-M1 work:

- foreign-script contamination in VI generated copy (Arabic/Hebrew fragments);
- `context_only` evidence being used as if it supported factual assertions;
- unsupported brand/editorial closing statements discovered late by Assertion Audit;
- repeated deterministic cleanup/re-audit recovery slices;
- high operator friction from terminal/manual lineage inspection;
- 14 ModelCalls for the first real bilingual Journal case;
- final review state distributed across drafts, audit/QE, Source-copy, approvals and ContentVersions rather than one operator surface.

These are evidence for targeted regression and UI work; they are not justification for a new workflow engine or broad architecture rewrite.

## MG closeout decision

All M1 acceptance conditions are satisfied on the current real local lineage.

**STATUS: M1 ONE REAL JOURNAL PASS — COMPLETE / CLOSED**

Next priority: T05.20 smallest useful Human Review Surface / Review Console, beginning with a read-only operator view over persisted real state. T05.18 targeted regressions remain required post-M1, but should not delay the first useful operator surface.