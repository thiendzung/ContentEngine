# PR4.5 — Founder Intake to Angle Vertical Slice

Date: 2026-09-14

Base main: `08a7a59140f6bfee42827347cb6d8b22a316b47f`

Branch: `ops/pr4-5-start-to-angle`

## Purpose

Deliver the first genuinely usable Journal operator vertical slice:

`Founder manual intake -> canonical NeedHypothesis/ContentOpportunity -> selected Journal ContentCase -> canonical required locales -> durable Start job -> bounded research/context/Angle execution -> WAIT_HUMAN(angle)`.

This PR starts from the merged OPS-02 control plane. It does not broaden arbitrary stage execution and does not claim full Journal autonomy.

## Architecture decisions

1. Founder manual intake is persisted as first-class planning data, not disguised as discovered market truth.
   - `NeedHypothesis.origin = founder_manual`;
   - NeedHypothesis remains `PROPOSED`;
   - one explicit `ContentOpportunity` is persisted with `decision=CREATE` and `selected_by=founder`;
   - no fake SEARCH/MARKET Signal is invented.
2. Required locales are canonical case requirements, separate from materialized `LocaleVariant` rows.
3. Journal default requirement for this slice is bilingual `vi` + `en`; source locale must be one of the required locales.
4. Operator callers continue to express intent only. They cannot choose `stage_key`, provider, model, worker, prompt, recipe, or retry implementation.
5. The backend prepares exactly one new bounded executable stage: `start_to_angle`.
6. `start_to_angle` is a durable Job/lease worker stage. HTTP persists/queues and returns; model/research work never runs inline in the request.
7. The worker owns the stage transition:
   - revalidate exact persisted case/run/step;
   - build/reuse bounded CE04/CE05 research/context inputs;
   - invoke the existing Angle model bridge using backend policy;
   - persist Angle candidates and telemetry;
   - complete the Job/Step;
   - set run `current_step=angle` and pause at the mandatory Angle human gate.
8. No silent fallback from real research/model failure to synthetic success. Missing prerequisites fail closed with stable codes.
9. Existing `review_revise_en` orchestration remains supported and unchanged in semantics.
10. Antigravity remains OPTIONAL/UNPROVEN. No publish/WordPress side effect.

## Required locale invariant

A new persisted required-locale ledger belongs to ContentCase. Materialization and completion are separate concepts:

- required locale exists even before its LocaleVariant is materialized;
- source LocaleVariant is materialized at create time;
- completion requires an approved/published ContentVersion for every persisted required locale;
- missing requirements must never be inferred from `len(locale_variants)`.

## Manual intake minimum contract

The Founder provides bounded editorial intent:

- project slug (default `motgu`);
- source locale;
- required locales;
- reader;
- situation;
- need / brief;
- primary question;
- intent;
- promise;
- selection reason.

The backend derives the canonical planning records and case/run identity. Idempotency must return the same intake/opportunity/case/run for the same key and reject same-key payload conflicts.

## Start-to-Angle execution contract

On a freshly created manual Journal case:

- operator state is `READY`, primary intent `start`;
- `start` queues exactly one durable Job for `start_to_angle`;
- worker claims the Job using existing lease primitives;
- one valid Angle artifact is produced from bounded, validated inputs;
- the Job and `start_to_angle` StepRun complete;
- the ContentRun becomes `waiting_approval` with `current_step=angle`;
- operator state becomes `AWAITING_APPROVAL`, `human_gate=angle`;
- there is no automatic Angle approval.

## Research boundary

Prefer existing approved evidence/originality snapshots when they are valid for the exact case. If the case requires new research, reuse the existing CE04 `ResearchRouter` / Evidence Research contracts with configured provider budgets. Search snippets are not evidence; only successfully read source material may become factual Evidence.

If a required research/originality prerequisite cannot be satisfied, the durable Job must fail closed. This PR must not fabricate an EvidenceSet, OriginalityPack, MOTGU-owned material, or Angle.

## Worker boundary

Add one supported generic local worker entrypoint that:

- claims a durable Job;
- dispatches only allow-listed stage executors;
- initially supports `start_to_angle`;
- preserves lease ownership and durable failure state;
- never accepts a caller-selected provider/model/stage;
- can later host the already-proven T05.22E route without changing operator semantics.

## Acceptance

1. migration round-trip passes;
2. Founder intake exact replay and same-key conflict behavior pass;
3. no fake signal/customer truth is created;
4. required locales persist separately from LocaleVariants;
5. source locale materializes once; untranslated required locale need not be materialized yet;
6. completion uses persisted required locales and remains false until every required locale has approved/published content;
7. new case state is READY/start with persisted `start_to_angle` StepRun and no Job;
8. start queues exactly one Job; replay creates no duplicate;
9. worker claim uses real Job lease and exact run/step binding;
10. worker success ends at `WAIT_HUMAN(angle)` with a real persisted Angle artifact;
11. worker failure is durable and fail-closed; no synthetic Angle;
12. human Angle approval remains explicit and separate;
13. no operator request accepts internal execution selectors;
14. frozen M1 is unchanged by automated tests;
15. no publish/external production side effect;
16. full `make check` and GitHub CI pass.

## Deferred

- Angle approval -> Outline execution;
- writer VI/EN execution;
- final bilingual completion UX;
- publish/WordPress;
- WebSocket/SSE;
- Antigravity activation;
- broad generic autonomous workflow engine.
