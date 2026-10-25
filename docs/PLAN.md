# PLAN - Content Production v1 RC1 for MOTGU

Effective 2026-10-25 for Issue #417. Current working window is `../AI_context.MD`. This plan keeps the proven ContentEngine architecture and narrows the active priority to **produce reviewable approved content packages for Founder manual WordPress publication**.

## Active business role

ContentEngine is the **content factory**, not the public CMS and not the business-operations system.

Its V1.1 job is:

```text
real customer/search question
→ evidence/originality
→ Angle
→ Outline
→ independent VI/EN Writer
→ Human Voice + quality
→ Founder final approval
→ approved ContentVersion / deterministic review package
→ Founder manual WordPress Draft / publish
```

For RC1, ContentEngine stops at the deterministic review package. Founder manually transfers the approved content into WordPress Draft, performs pre-publish QA/QC and publishes.

No direct ContentEngine write to WordPress, WooCommerce, MOTGU production data, Git or Astro. Publication automation is out of scope.

## Current critical path

1. Verify Content Production v1 RC1 on one exact candidate SHA.
2. Produce the MAP-v3 batch **G01/G02/Q05/Q07/Q06** through the existing human gates.
3. Produce exact approved ContentVersions/review packages with hashes, provenance, intent owner, `must_not_claim`, metadata and internal-link plan.
4. Stop at deterministic package; Founder manually creates/reviews the WordPress Draft.
5. Apply the 14-point pre-publish check and content-type QA gates before manual publication.
6. Use real Search Console/Bing/inquiry observations after publication; do not reopen architecture or strategy work without evidence.

## Development admission rule

A ContentEngine code change is allowed during this campaign only for:

- a data-integrity/security defect;
- a canonical workflow blocker;
- a repeated defect observed in at least two real cases;
- one severe single-case defect preventing truthful completion;
- the minimum deterministic MOTGU handoff/export boundary if no existing safe path exists.

Otherwise log the observation and continue production.

Explicitly deferred:

- new provider/framework;
- Antigravity product dependency;
- broad dashboard/UI redesign;
- generic workflow engine;
- speculative prompt refactor;
- WordPress/Rank Math activation for MOTGU;
- auto-publish;
- new Question Map implementation;
- strategy automation not driven by real post-publication data.

## Delivery milestones for V1.1

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| **CF-1 — Real batch** | P01/C02/C03/C05/P02 complete in VI+EN | exact stable release, approvals, hashes, quality evidence, no case-specific bypass |
| **CF-2 — Handoff** | approved package can enter MOTGU OPS safely | deterministic/idempotent package, no model call, exact provenance, OPS validation |
| **CF-3 — Public proof** | one Golden article completes OPS → Git → Astro | verified public URL and release evidence |
| **CF-4 — Batch release** | remaining approved pilot content published | public URLs, internal links/CTA, no duplicate publish |
| **CF-5 — Learning input** | real external observations can map back to content identity | observed data only; no automatic causality or truth promotion |

No calendar promises. Gate evidence determines completion.

## Historical roadmap status

CE00–CE09 modules, Customer Living Map, QA, PM/LL, UI and Question Map work remain valid architecture/history. They are **not an active implementation queue merely because open checkboxes remain in historical sections**.

Question Map V1 is closed and maintenance-only.

The older M1–M4 / WordPress-placement wording below is retained only where needed for historical traceability; it does not override the active MOTGU V1.1 Astro handoff described above.


## Historical delivery order

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

For MOTGU V1.1, M3-style placement means the simplest approved **MOTGU OPS Content Release → Git → Astro** handoff. Do not activate the historical WordPress adapter for the MOTGU showroom.

M4-style learning starts from real editorial/traffic/lead observations. A failed article or weak market response may improve the test set without becoming a global rule. A failed article can improve the test set without becoming a global rule.

## Mapping to the existing CE roadmap

| CE phase | Retained scope | Delivery policy |
|---|---|---|
| CE00-CE04 | Contracts; walking skeleton; data/settings; durable harness; production research | Previously CLOSED/PASS; do not rebuild |
| CE05 | Journal context/research, Angle/Outline, independent writers, checks/package, review surface, metrics, closeout | M1 first; applicable T05.18-T05.22 in M2 |
| CE06 | Full quality evaluators, Golden/Weak sets and pairwise regression | Start with small real-case regressions; expand by evidence |
| CE07 | Artwork canonical facts, media, artist context, independent writers and gates | Not opened by this plan |
| CE08 | Historical publishing adapters and measurement mapping | For MOTGU V1.1 use the bounded OPS/Git/Astro handoff; do not activate WordPress/Rank Math unless explicitly reopened |
| CE09 | Content memory, overlap, edit delta, learning lifecycle and 1/3/6-month review | Capture records now; automate by measured need |
| CE10 | Intentional 10-20-hypothesis pilot and roadmap review | After repeatable local delivery; not a volume quota |

This delivery order replaces the assumption that every full CE06/CE07 feature must precede first Journal placement. It does not renumber tasks, erase historical work or weaken hard gates. The prior phase plan is preserved at `logs/2026-09-12-plan-before-local-first.md` as history, not the active schedule.

## Change selection rule

Every proposed change states: observed problem, affected outcome, smallest fix, evidence of success, rollback, and what is deliberately NOT being built. Before M1 it must directly unblock the current real Journal or fix demonstrated security/data-integrity risk. Otherwise it stays in backlog.

## Approved next architecture track — Customer Living Map + Controlled Autopilot

Canonical contract: `21-CUSTOMER-LIVING-MAP-AUTOPILOT-SPEC.md`.

This track extends the proven Journal foundation. It does not erase M1-M4, authorize a local migration, or permit model/runtime execution merely because the roadmap exists.

| Order | ID | Deliverable | Exit evidence |
|---|---|---|---|
| 0 | ARCH-21 | Contract/plan sync | Spec + PLAN + TASKS + CHECKLIST + AI_context agree |
| 1 | CT-01 | CustomerInsight foundation | Signal → Insight with provenance, support/contradiction, versioning and tests |
| 2 | AU-01 | ExecutionPlan + capability policy | Every automated task has bounded scope, permissions, retries, budget and stop rules |
| 3 | CM-01 | Customer Living Map | Audience/Needs/Journey snapshot + incremental change API |
| 4 | CC-01 | Content Coverage | Need ↔ Content ↔ Journey coverage/gap map |
| 5 | LS-01 | Lens Selection | 7-lens candidates with SELECT/MERGE/HOLD/DROP and evidence guards |
| 6 | AU-02 | Agent Bridge + orchestration | Approved plan auto-runs safe next tasks through existing Harness with independent review |
| 7 | QA-01 | Reader Value + SEO/AI readiness | Reader Value is prerequisite; discovery readiness is separate |
| 8 | PM-01 | Publish + measurement identity | Published URL/version maps back to audience/need/journey/lens |
| 9 | LL-01 | Closed learning loop | Observation → candidate → experiment → regression → reviewed promotion |
| 10 | UX-01 | Control Center + Living Map UI | Overview/Customers/Content Map/Production/Needs Me/Learning/System |
| 11 | E2E-01 | Real closed-loop pilot | One real case completes the full loop without case-specific bypass |

Question Map / Founder UI closeout — 2026-10-08:
- QM-01A/B/C/D derived planning chain is complete;
- QM-02A/B/C/D1 plus F1 readiness/search/architecture remediation are complete;
- QM-02D2 UPDATE/REFRESH and QM-02D3 MERGE handoffs are complete;
- QM-02E Founder UI is complete;
- QM-02F / #361 Golden E2E is CLOSED with `PASS_QM02_GOLDEN_CLOSEOUT`;
- UI-P1 / PR #373 through UI-P6 / PR #410 are complete and merged;
- Question Map V1 is now maintenance-only: no new QM implementation is implied by this roadmap;
- reopen QM only for a demonstrated defect, real-data learning, or an explicit Founder product decision.

### Question Map V1 consolidated chain — CLOSED

```text
QM-01A  canonical Question Map read model
→ QM-01B locale-aware classification + answer-job clustering
→ QM-01C Content Coverage join
→ QM-01D read-only Opportunity Planner
→ QM-02A explicit Founder selection handoff
→ QM-02B deterministic production route
→ QM-02C read-only admission
→ QM-02D1 CREATE handoff
→ F1R0/R1/R2/R3 two-axis readiness + architecture + bounded real Search
→ F1C architecture checkpoint
→ QM-02D2 UPDATE / REFRESH
→ QM-02D3 MERGE reconciliation
→ QM-02E Founder UI
→ QM-02F Golden E2E
→ UI-P1..P6 Founder operating polish
```

Boundary note:
- QM-02F / #361 proves the **Question Map planning-to-materialization Golden E2E**.
- It does **not** close the broader ContentEngine E2E-01 / #201 loop that includes real production, publish, measurement and learning; #201 remains a separate track.

Final invariants:
- Question Map is derived planning, not a second Customer Truth or keyword truth store;
- Customer Truth confidence and Content Readiness remain separate;
- Search/PAA/Related/Autocomplete are planning signals, not factual Evidence;
- Founder selection remains explicit;
- route/admission/materialization remain backend-authoritative and fail closed;
- CREATE/UPDATE/REFRESH/MERGE do not auto-Start/Writer/Publish;
- future QM changes require demonstrated evidence, not roadmap momentum.

Execution rules:
- The ARCH-21 -> CT-01 -> ... sequence above is retained as architecture/history, not a current QM task queue.
- Question Map V1 is closed; do not restart from historical unchecked boxes.
- Do not interleave new schema/runtime mutation with an active content execution.
- WIP stays one implementation plus one related verification.
