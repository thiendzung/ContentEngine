# QM-02A — Selected Planner Handoff

Date: 2026-10-06  
Tracking: issue #338  
Branch: `feat/qm-02a-selected-handoff`  
Base: `c078de099c4bc22bed3f239b23b537b0c294924e`

## Goal

Move from “the planner knows what should happen” to “the Founder selected one exact
recommendation and that choice now exists in canonical durable planning state.”

```text
QM-01D exact planner snapshot
+ one exact cluster
+ explicit Founder/editorial brief commitments
+ explicit human selection
→ ContentOpportunity
→ exactly one HumanSelection
```

This slice stops there.

## Reverse-design decision

Two existing paths were inspected and deliberately not reused as the QM-02A authority.

### Old discovery persistence

`research/discovery/persistence.py` persists the historical in-memory
`OpportunityMapResult` and can create a ContentExperiment draft after selection.

QM-02A does not rebuild an old OpportunityMapResult just to reuse that API. Doing so would
turn the legacy planning object back into an authority beside the merged Question Map /
Coverage / Planner v2 chain.

### Founder manual Journal intake

`operator_manual_intake.py` creates a new `founder_manual` NeedHypothesis, immediately
creates a ContentCase and approves a Founder-submitted OriginalityPack.

That is correct for manual editorial intake but wrong for QM-02A, because the planner is
already bound to an existing canonical customer Need. Reusing manual intake would duplicate
customer truth.

Therefore QM-02A persists only the missing canonical handoff objects:
`ContentOpportunity + HumanSelection + ContentOpportunitySignal links`.

## Editorial data that must not be invented

QM-01D intentionally does not fabricate:

- a strong editorial promise;
- Founder/editorial coverage commitments;
- approved MOTGU-owned material;
- proven new/original value.

The POST therefore requires explicit human input for:

- `promise`;
- 1..12 ordered `coverage_requirements`;
- `selection_reason`;
- actor identity.

Everything that is already canonical comes from the exact current state, not the request:

- Need / reader scope / situation from `NeedHypothesis`;
- question / intent / decision / priority / target refs from the exact planner recommendation;
- SEARCH support lineage from the exact Question Map cluster.

The client cannot override decision, priority, question, intent, Need or target refs.

## Safe placeholder semantics

Because QM-01D keeps `right_to_win_proven=false`, QM-02A persists:

- no `motgu_material_refs_json`;
- an explicit material gap;
- `what_is_actually_new` = not established yet;
- a next step requiring locked EvidenceSet + approved OriginalityPack before Lens/Angle.

This is intentionally weaker than claiming differentiation that has not been proved.

## Exact selection gate

The write requires:

1. existing canonical Need in the requested project;
2. row lock on that Need to serialize concurrent selection for the same Need;
3. exact current planner `snapshot_hash`;
4. exact `cluster_key`;
5. `selection_readiness=READY_FOR_HUMAN_SELECTION`;
6. valid primary ContentItem refs for UPDATE / REFRESH / MERGE / LINK_ONLY;
7. exact supporting SEARCH Signal lineage for the Need/project/locale.

`REUSE_EXISTING_PLAN`, `RESEARCH_REQUIRED`, `BLOCKED` and `DO_NOT_WRITE` do not create
a new durable plan.

## Replay / idempotency

The ContentOpportunity and HumanSelection IDs are deterministic from:

`planner_snapshot_hash + cluster_key`.

Important nuance: after first persistence, Content Coverage changes, so the next live planner
snapshot normally changes. Exact replay therefore checks for the deterministic already-persisted
selection **before** requiring the old planner hash to still be current.

Exact replay returns the original receipt. A changed promise, coverage commitment, actor or
selection reason conflicts instead of silently rewriting the durable selection.

A genuinely unseen stale planner snapshot still fails before persistence.

## Durable lineage

`ContentOpportunity.reasons_json` retains bounded lineage markers:

- exact planner snapshot hash;
- planner policy version;
- cluster key;
- Question Coverage snapshot hash;
- planner reason codes.

This is audit lineage, not a second planner truth store.

## API

New mutation endpoint:

`POST /question-map/opportunities/select`

Request includes:

- project_slug;
- need_id;
- locale;
- cluster_key;
- expected_planner_snapshot_hash;
- selected_by;
- selection_reason;
- promise;
- ordered coverage_requirements.

Response is a compact immutable-style receipt containing the durable opportunity/selection IDs,
planner hash, cluster key, decision, priority and replay flag.

## Intentionally excluded

- no new NeedHypothesis;
- no ContentExperiment;
- no ContentCase / LocaleVariant;
- no Lens/Angle/workflow/run/job;
- no model/provider/tool call;
- no publication;
- no UI;
- no DB table/model/migration;
- no operational DB mutation.

## Verification target

Agent Local exact-SHA verification must prove:

- Ruff + mypy;
- QM-01A/B/C/D regressions + QM-02A focused tests;
- existing discovery-selection and Content Coverage regressions;
- full backend with provider/model/search keys blank;
- transaction-backed write proof with rollback;
- exact replay after live coverage/planner changes;
- stale unseen snapshot fails;
- non-ready recommendation fails;
- primary UPDATE target is preserved;
- no duplicate plan after REUSE_EXISTING_PLAN;
- no ContentExperiment/ContentCase creation;
- exact-ref OpenCodeReview;
- minimal GitHub CI when available.

Founder remains merge authority.
