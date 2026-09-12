# PLAN - ContentEngine finish-first delivery

Effective after Founder merges the 2026-09-12 local-first contract. Implementation status is in `TASKS.md`; the current working window is `../AI_context.MD`. Requirements: `20-LOCAL-FIRST-DELIVERY-SPEC.md`, foundational specs 00-12 and Journal spec 19.

## Delivery order

| Milestone | Deliverable | Exit evidence | Not a prerequisite |
|---|---|---|---|
| M1 - finish | One real Journal VI/EN approved on the Founder's local runtime | Valid current lineage, three editorial approvals, hard-clean checks, package with hashes, final approval | New infrastructure/provider, WordPress, broad hardening |
| M2 - repeat | Three distinct real Journal cases total, including M1 | Last two on the same merged runtime version without case-specific code; safe resume; separate test DB; backup/restore; small operator path | Full dashboard, generic runner, cloud deployment |
| M3 - place and measure | Safe manual Journal placement and traceable measurement baseline | URL/external ID bound to approved ContentItem/Version and hypothesis; observations or explicit insufficient data | Full Artwork engine, full analytics automation, auto-publish |
| M4 - improve from evidence | Controlled editorial and audience learning | Frozen baseline/candidate comparison, human edits, negative cases, approved changes with rollback | Automated strategy changes |

No calendar promises. Gates, not elapsed days or PR count, determine progress. M2-M4 are PLANNED, not authorized execution tasks. Per-run feedback capture starts now.

## Immediate M1 sequence

1. LF-01: Agent Local verifies the current DB/input bindings and classifies the Angle blocker in one read-only evidence packet. No research, model generation, content approval or runtime writes.
2. LF-02: MG reviews that evidence. If code is defective, make one bounded fix with focused tests and related local verification. If only permission/invocation is wrong, resolve it without inventing a code change. Do not bypass safeguards.
3. LF-03: issue one bounded runtime task covering all authorized Journal steps until an actual editorial decision or conclusive blocker. Reuse the SAME fresh run and bundle. Budget, expected refs and allowed actions must be explicit.
4. LF-04: produce Operational Package V0, complete applicable checks, obtain Founder final approval and bind it to final bytes. Close M1 only with real local evidence.

No PR for each shell command. A code change and its tests, relevant evidence and semantic transition belong in one coherent PR. Runtime-only evidence can be batched at a material gate. Never merge or silently advance a gate to reduce paperwork.

## After M1

Prioritize M2 work by the first real bottleneck: existing-script entrypoint, actionable failure reporting, local/test isolation, backup/restore, safe restart/resume. Investigate duplicated context and usage capture only with a before/after check. Do not turn every suggested improvement into mandatory work before the next article.

Use human review burden, approved output and repeated failures as the first baseline. Record latency/calls and known usage too; do not manufacture monetary estimates for missing CLI telemetry.

In M3 prefer the simplest approved manual placement before building the complete WordPress adapter. Preserve final version/URL identity, media rights, approval and check references. Capture real observations; do not infer demand or success from an AI score.

M4 starts with editorial batches and only later audience/strategy changes when evidence is sufficient. A failed article can improve the test set without becoming a global rule.

## Mapping to the existing CE roadmap

| CE phase | Retained scope | Delivery policy |
|---|---|---|
| CE00-CE04 | Contracts; walking skeleton; data/settings; durable harness; production research | Previously CLOSED/PASS; do not rebuild |
| CE05 | Journal context/research, Angle/Outline, independent writers, checks/package, review surface, metrics, closeout | M1 first; applicable T05.18-T05.22 in M2 |
| CE06 | Full quality evaluators, Golden/Weak sets and pairwise regression | Start with small real-case regressions; expand by evidence |
| CE07 | Artwork canonical facts, media, artist context, independent writers and gates | Not opened by this plan |
| CE08 | WordPress draft/version mapping, reconciliation and measurement adapters | M3 may take a small manual Journal handoff/identity slice first; full phase remains open |
| CE09 | Content memory, overlap, edit delta, learning lifecycle and 1/3/6-month review | Capture records now; automate by measured need |
| CE10 | Intentional 10-20-hypothesis pilot and roadmap review | After repeatable local delivery; not a volume quota |

This delivery order replaces the assumption that every full CE06/CE07 feature must precede first Journal placement. It does not renumber tasks, erase historical work or weaken hard gates. The prior phase plan is preserved at `logs/2026-09-12-plan-before-local-first.md` as history, not the active schedule.

## Change selection rule

Every proposed change states: observed problem, affected outcome, smallest fix, evidence of success, rollback, and what is deliberately NOT being built. Before M1 it must directly unblock the current real Journal or fix demonstrated security/data-integrity risk. Otherwise it stays in backlog.
