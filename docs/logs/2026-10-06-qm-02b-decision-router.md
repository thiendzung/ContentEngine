# QM-02B — Production Decision Router

Date: 2026-10-06  
Tracking: issue #340  
Branch: `feat/qm-02b-decision-router`  
Base: `164824ceb178febccf26f675ca14884c4d1d825f`

## Goal

Convert one already-selected durable ContentOpportunity into one deterministic production
route without creating production state.

```text
selected ContentOpportunity
+ exactly one matching HumanSelection
+ exact target ContentItem lineage
→ deterministic route
```

Routes:

- CREATE -> CREATE_NEW_CONTENT
- UPDATE -> REVISE_EXISTING_CONTENT
- REFRESH -> REFRESH_EXISTING_CONTENT
- MERGE -> RECONCILE_CONTENT
- LINK_ONLY -> NO_PRODUCTION
- DO_NOT_WRITE -> STOP

## Reverse-design decision

QM-02B is deliberately a read model.

The next real risk is not missing another table. It is accidentally treating every selected
opportunity as “create a new article”. The existing Journal operator already protects one
important boundary: `create_or_reuse_journal_case` refuses any opportunity whose decision is
not CREATE.

QM-02B therefore does not weaken or duplicate that operator guard. It makes the decision
routing explicit before the future production-admission write boundary.

## Authority checks

The route is valid only when:

1. the opportunity exists in the requested project;
2. its content type is Journal;
3. exactly one durable HumanSelection exists;
4. HumanSelection matches the convenience selection fields on ContentOpportunity;
5. target refs parse as unique UUIDs;
6. CREATE has zero targets;
7. UPDATE / REFRESH / LINK_ONLY have exactly one target;
8. MERGE has at least two targets;
9. DO_NOT_WRITE has zero targets;
10. every target ContentItem exists in the same project;
11. every target ContentItem belongs to a ContentCase whose **primary Need** is the same
    canonical Need as the selected opportunity;
12. every target LocaleVariant matches the selected opportunity locale.

Supporting-Need-only content therefore cannot become an UPDATE/REFRESH/MERGE/LINK_ONLY
production target.

## Route semantics

### CREATE_NEW_CONTENT

Candidate for QM-02C production admission. It still does not create a ContentCase here.

### REVISE_EXISTING_CONTENT

Candidate for a revision path bound to the exact existing ContentItem. It must not create a new
canonical article merely because a new selected opportunity exists.

### REFRESH_EXISTING_CONTENT

Same target identity discipline as UPDATE, but refresh semantics remain distinct for downstream
admission/revision logic.

### RECONCILE_CONTENT

MERGE is not automatic model merging. QM-02B reports reconciliation required and does not mark
the route as an admission candidate.

### NO_PRODUCTION

LINK_ONLY is durable planning/audit state only. It must not create a ContentCase or run.

### STOP

DO_NOT_WRITE is terminal for production routing.

## API

Read-only endpoint:

`GET /question-map/opportunities/{opportunity_id}/route?project_slug=...`

The response includes:

- opportunity + selection + Need identity;
- decision;
- exact route;
- exact target ContentItem IDs;
- admission/reconciliation/forbidden booleans;
- reason codes;
- deterministic snapshot hash.

## Intentionally excluded

- no ContentCase creation;
- no ContentVersion creation;
- no ContentExperiment;
- no admission record;
- no run/job/workflow;
- no provider/model/tool call;
- no publication;
- no UI;
- no DB model/table/migration.

## Next slice

QM-02C Production Admission should consume this route, revalidate it exactly, and create only
the minimum execution binding appropriate to the route. CREATE should be implemented and
piloted before UPDATE/REFRESH/MERGE write paths are expanded.
