# QM-01C — Question Map × Content Coverage join

Date: 2026-10-05
Tracking: issue #333
Branch: `feat/qm-01c-question-coverage-join`
Base: `b01849bbf4028c1e6a21b2c41248cdb643b597cb`

## Goal

Join the merged Question Map v2 read model with canonical Content Coverage without creating a second truth store:

```text
Question cluster
= canonical Need + locale + intent + answer_job
                    │
                    ├─ Content Coverage items
                    └─ selected ContentOpportunity planning state
                              ↓
                 derived cluster coverage
```

## Authority boundary

QM-01C is a read-only derived join.

Canonical / pre-existing authorities remain:

- `NeedHypothesis` and supporting `SEARCH` Signals for Question Map;
- existing Content Coverage for content/publication/revision/planning facts;
- existing `LocaleVariant.primary_question / primary_intent` and selected
  `ContentOpportunity.question / intent` as the candidate language to join.

QM-01C does not:

- create a keyword/question truth table;
- add a migration or SQLAlchemy model;
- mutate/create ContentOpportunity;
- change legacy OpportunityMap behavior;
- change Content Coverage semantics;
- call a model/provider;
- add UI;
- publish or run operational workflow.

The existing `GET /question-map` response remains unchanged. QM-01C adds a separate
read projection:

`GET /question-map/coverage?project_slug=...&need_id=...&locale=...`

## Matching contract

Existing item/opportunity candidate language is classified with the same deterministic
Question Map v2 classifier. A candidate can match a cluster only when:

1. locale matches after normalized comparison;
2. stored intent matches cluster intent;
3. v2 classification is classified + usable;
4. classifier intent still matches stored/cluster intent;
5. classifier answer_job equals cluster answer_job.

Unresolved/truncated/off-scope candidates never count as answered.

A same-intent candidate that cannot be safely classified is retained as unresolved evidence.
If no safe match exists, the cluster returns `INSUFFICIENT_DATA` rather than a false MISSING.

## Cluster coverage states

- `ANSWERED`: one matching primary ContentItem has a current published version.
- `STALE`: matching primary published content has a newer unpublished revision or is the
  explicit target of a selected UPDATE/REFRESH.
- `COLLISION`: more than one matching primary ContentItem competes for the same cluster;
  when no item exists, multiple matching selected CREATE plans also count as collision.
- `PARTIAL`: matching work/plan exists but no current primary published answer; a
  supporting-Need published item is also partial rather than primary answered coverage.
- `MISSING`: no matching safe item or selected write plan exists.
- `INSUFFICIENT_DATA`: same-intent candidate evidence exists but cannot be safely
  classified/matched.

Precedence is intentionally:

`COLLISION -> STALE -> ANSWERED -> PARTIAL -> INSUFFICIENT_DATA -> MISSING`

This prevents a published item from hiding a collision or explicit stale/update condition.

## Primary safety rules

- A published ContentItem means coverage exists; it does **not** mean the customer problem
  is solved.
- Supporting-Need coverage does not become a primary answer.
- DO_NOT_WRITE does not count as coverage.
- Cross-locale state does not match.
- Existing Content Coverage and Question Map are read; no durable state is mutated.
- The join has its own deterministic `snapshot_hash`; it references, but does not replace,
  the Question Map `snapshot_hash`.

## Verification required

Agent Local exact-SHA:

- `git diff --check`;
- Ruff + mypy targeted modules;
- QM-01A/B regression + QM-01C focused tests;
- existing CC-01 regressions;
- legacy OpportunityMap regressions;
- full backend with provider/model/search keys blank;
- disposable read-only API proof;
- exact-ref OpenCodeReview;
- confirm no migration/model/provider/ContentOpportunity/runtime/publication mutation.

Founder remains merge authority.
