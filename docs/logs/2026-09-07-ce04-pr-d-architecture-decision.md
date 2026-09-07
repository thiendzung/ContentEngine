# CE04 PR-D — Architecture Decision: Pre-ContentCase Discovery Durability

Date: 2026-09-07
PR: `#26 — CE04 PR-D — Discovery Research + Opportunity Handoff`

## Problem

Canonical architecture orders planning as:

```text
NeedHypothesis
→ Knowledge Recall
→ Discovery Research
→ Opportunity Map
→ Human Selection
→ ContentCase + LocaleVariant
→ Evidence Research
→ Durable ContentRun harness
```

Current `ContentRun` schema requires non-null `content_case_id`, `locale_variant_id` and `settings_snapshot_id`.

Therefore a pre-selection Discovery run cannot truthfully create a `ContentRun` without inventing a ContentCase/LocaleVariant that does not yet exist.

## Decision

PR-D MUST NOT create fake ContentCase / LocaleVariant / ContentRun / StepRun records merely to satisfy durable telemetry or Artifact foreign keys.

The production behavior is split deliberately:

### A. Pre-ContentCase Discovery / real PR-D gate

Run the production `ResearchRouter` without run/step IDs.

This still uses the router's bounded transient provider budget and canonical stop rules.

Write one bounded, versioned JSON Discovery artifact containing:

- research request and stop reason;
- provider decisions and provenance;
- normalized SEARCH/MARKET/MOTGU planning signals;
- source metadata (`source_type`, `commercial_bias`, contextual `authority_hint`);
- Question/Opportunity Map;
- research gaps;
- `artifact_type = discovery_research_report`;
- `evidence_eligible = false`.

This gate artifact is a planning/research artifact, not factual Evidence.

### B. Durable ContentRun binding when a legitimate run exists

If a later workflow already has a real ContentCase/LocaleVariant and supplies legitimate `run_id` + `step_run_id`, the same Discovery workflow may:

- reuse CE03 ToolCall/budget ledger through the existing ResearchRouter;
- persist a harness `Artifact` bound to that exact StepRun;
- expose the real artifact ID for ContextManifest/tool-result refs.

Database-backed integration tests may create synthetic fixture records to prove this binding behavior. Such fixtures are test data only and are not the production pre-ContentCase path.

## Why

This preserves both canonical truths:

1. Discovery and Opportunity planning happen before human-selected ContentCase creation.
2. CE03 remains the durable harness when a valid ContentRun exists.

It also preserves the PR-C architecture review rule:

> Standalone real-provider gates do not create fake ContentRun/StepRun records just to satisfy telemetry shape.

## Non-decisions

PR-D does NOT:

- make `ContentRun.content_case_id` nullable;
- add a new generic `ResearchRun` table;
- add a second queue/worker/budget ledger;
- persist Discovery as factual Evidence;
- begin T04.18 Evidence Research.

Any future need for a durable pre-ContentCase run identity requires an explicit contract change with real operational evidence.

## Gate consequence

The PR-D real gate must prove the standalone pre-ContentCase path.

Separately, integration tests must prove the optional legitimate ContentRun binding path.
