# QM-01A — Canonical Question Map read model

Date: 2026-10-05
Tracking: issue #329
Branch: `feat/qm-01a-canonical-question-map`
Base: `a0c4147b971da357d5c0ffe7ae759dd6f30a1518`

## Goal

Implement the smallest derived Question Map slice:

`canonical Need + existing SEARCH Signals -> deterministic locale-specific read model -> snapshot_hash -> read-only API`

## Authority boundary

Question Map is not a new source of truth.

Canonical inputs:
- `NeedHypothesis`
- `NeedHypothesisSignal`
- persisted `Signal` rows where `source_kind=SEARCH`

QM-01A does not:
- create or revise NeedHypothesis;
- create ContentOpportunity;
- call a model;
- add a migration/table;
- mutate production workflow state;
- classify intent/topic;
- cluster by answer job;
- add UI.

## Derived contract

Endpoint:

`GET /question-map?project_slug=<slug>&need_id=<uuid>&locale=<locale>`

Output includes:
- project identity;
- canonical Need identity/version/status;
- exact locale;
- deterministic normalized question rows;
- source Signal IDs per row;
- aggregate Signal IDs;
- explicit counts;
- stable SHA-256 `snapshot_hash`.

Only `supports` links from SEARCH Signals are consumed. MARKET/MOTGU signals, contradictions, foreign projects and other locales are excluded.

Same normalized search language is deduplicated into one row while retaining all source Signal refs.

## Verification required

Agent Local exact-SHA:
- targeted `pytest -q backend/tests/test_qm01a_question_map.py`;
- relevant customer-map / keyword-plan regressions;
- full backend tests if targeted checks pass;
- no migration expected;
- read-only API smoke against disposable/test state;
- exact-ref OpenCodeReview;
- confirm no ModelCall/ToolCall or operational mutation.

Founder remains merge authority.
