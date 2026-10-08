# Question Map V1 — Consolidated Closeout

Date: 2026-10-08  
Base main: `0754306bf4c6d1ec539db5e57e896c20aeba4bad`  
Cleanup tracker: #411  
Branch: `docs/qm-v1-consolidated-closeout`

## Review conclusion

There is no unfinished Question Map V1 implementation.

The remaining inconsistencies were planning/bookkeeping drift:

- stale active UI-P6 wording after PR #410 merged;
- stale parent #337 left open even though #338 implemented the final QM-02A contract;
- historical #362 checklist text still showing old unchecked Golden items despite #361 being closed with accepted closeout;
- duplicate Business-first contract text in spec 21;
- no single active plan section showing the complete QM planning-to-materialization chain.

Historical logs and closed issue bodies remain evidence and are not rewritten as if they were live plans.

## Consolidated chain

```text
QM-01A  canonical Question Map read model
→ QM-01B locale-aware classification + answer-job clustering
→ QM-01C Content Coverage join
→ QM-01D read-only Opportunity Planner

→ QM-02A explicit Founder selection
→ QM-02B deterministic production route
→ QM-02C read-only admission
→ QM-02D1 CREATE handoff

→ F1R0 two-axis architecture lock
→ F1R1 Content Readiness decoupled from Customer Truth status
→ F1R2 deterministic Pillar / Cluster architecture
→ F1R3 bounded real Search discovery
→ F1C architecture checkpoint

→ QM-02D2 UPDATE / REFRESH handoff
→ QM-02D3 MERGE reconciliation
→ QM-02E Founder UI
→ QM-02F Golden E2E

→ UI-P1 persistent navigation
→ UI-P2 Question Map decision cockpit
→ UI-P3 Vietnamese Founder layer
→ UI-P4 business-first information hierarchy
→ UI-P5 Production Board operations/density
→ UI-P6 global visual system
```

## Issue reconciliation

| Stage | Tracking evidence | Closeout |
|---|---|---|
| QM-01A | #329 / #330 | closed |
| QM-01B | #331 / #332 | closed |
| QM-01C | #333 / #334 | closed |
| QM-01D | #335 / #336 | closed |
| QM-02A | #337 parent + #338/#339 implementation | #338 complete; #337 superseded |
| QM-02B | #340 / #341 | closed |
| QM-02C | #342 / #343 | closed |
| QM-02D1 | #344 / #345 | closed |
| early real CREATE | #346 | closed |
| two-axis architecture | #353 / #354 | closed |
| Pillar / Cluster | #355 | closed |
| bounded real Search | #356 | closed |
| architecture checkpoint | #357 | closed / PASS |
| UPDATE / REFRESH | #358 | closed |
| MERGE | #359 | closed |
| Founder UI | #360 | closed |
| Golden E2E | #361 | closed / `PASS_QM02_GOLDEN_CLOSEOUT` |
| completion tracker | #362 | closed |
| UI-P1 | #372 / PR #373 | merged |
| UI-P2 | #374 / PR #375 | merged |
| UI-P3 | #378 / PR #379 | merged |
| UI-P4 | #389 / PR #396 | merged |
| UI-P5 | #397 / PR #403 | merged |
| UI-P6 | #404 / PR #410 | merged |

## Scope boundary

QM-02F / #361 is the Question Map Golden E2E: Search/Question Map/Architecture/Founder decision/route/admission/materialization.

It does **not** close the broader ContentEngine E2E-01 / #201 loop. #201 remains separate/open because it covers the full production/publish/measurement/learning closed loop.

## Canonical invariants retained

1. Question Map is a derived planning projection, not an independent truth store.
2. Customer Truth confidence and Content Readiness are separate axes.
3. Search/PAA/Related/Autocomplete/organic context are planning signals, not factual Evidence.
4. Founder selection is explicit authorization, not truth evidence.
5. Route, admission and materialization remain backend-authoritative and fail closed.
6. CREATE / UPDATE / REFRESH / MERGE do not auto-Start, auto-Writer or auto-Publish.
7. Pillar/Cluster architecture is deterministic and locale-specific; no Pillar is forced when breadth is insufficient.
8. MERGE is reconciliation planning, not destructive automatic merge.
9. Future Search expansion must not widen beyond the bounded posture without evidence.
10. A new QM task requires a demonstrated defect, real-data learning or an explicit Founder product decision.

## Cleanup performed

- consolidate QM V1 state in PLAN;
- reconcile TASKS with completed P6 and completed QM chain;
- clear stale P6-active / QM-next-task wording in AI_context;
- add explicit QM V1 closeout to Opportunity Map spec;
- mark Definition of Done V1 as satisfied by Golden E2E;
- deduplicate the Business-first hierarchy block in spec 21;
- close stale #337 as superseded by #338 + downstream exact proof.

## Non-goals

- no runtime/code behavior change;
- no API/schema/DB migration;
- no new Search run;
- no provider/model call;
- no reopening historical closed issues merely to edit checkbox history;
- no new QM phase.

## Result

`PASS_QM_V1_PLAN_CONSOLIDATION`

Question Map V1 is closed and maintenance-only.
