# CE04 PR-D — Founder Selection

Date: 2026-09-07
Phase: CE04
PR: #26 — CE04 PR-D — Discovery Research + Opportunity Handoff
Branch: `ce04-discovery-opportunity-handoff`

## Decision

Founder selected:

```text
O4 — Artsy prices
```

Planning opportunity ID:

`opp_4c397247e40db8ae`

Persisted ContentOpportunity ID:

`068991ab-de34-4787-9c38-8935c3f0e2da`

Source Discovery artifact:

`artifacts/research/ce04-discovery-research-v1-20260907T115027Z.json`

Expected SHA-256:

`489d4c3b91c06d84345c7b66729d69a9a91b45a419f889853d628b14b09927f7`

Persisted NeedHypothesis ID:

`530bdd27-f008-4910-9b3b-df83e007cfa2`

## Meaning of the selection

This selects the price-evaluation opportunity represented by O4 for the next ContentEngine handoff.

It does NOT mean:

- `Artsy prices` is approved as a final article title;
- search results are factual Evidence;
- the NeedHypothesis is confirmed;
- MOTGU must publish content before Evidence Research;
- PR-E may start before PR-D is closed.

The preferred human-facing framing remains closer to:

`How do I know if an original artwork is fairly priced?`

That framing is guidance only; the canonical selected object remains O4 / `opp_4c397247e40db8ae`.

## Selection reason to persist

Use exactly:

`Founder selected O4 because it best matches the first-time buyer price-evaluation need and has the strongest repeated search support among READY opportunities. Selection is a research/content direction, not factual approval.`

Use:

`selected_by = founder`

## Required persistence result

The selection step must:

- load the exact saved Discovery artifact;
- verify the exact SHA-256 before selection;
- select exactly `opp_4c397247e40db8ae`;
- call zero research providers;
- persist one HumanSelection;
- persist/reuse one ContentExperiment draft for the selected opportunity;
- keep NeedHypothesis status = `PROPOSED`;
- not create ContentCase;
- not create ContentRun;
- leave PR #26 Draft;
- leave T04.15–T04.17 unchecked until MG CONTENT ENGINE verifies the persisted result and final-head CI.

## Boundary

This is the founder human-selection gate for PR-D only. It is not Evidence approval and not Knowledge admission.
