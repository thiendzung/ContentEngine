# Content Production v1 RC1

**Release type:** bounded release candidate  
**Publication mode:** Founder manual WordPress Draft/publish  
**Production-ready v1.0.0:** **No**  
**Real Q07 runtime gate:** **Not yet passed on this final release candidate**

## What is included

- Beginner-oriented Content Production operator UX.
- Desktop/tablet final polish for 1440px and 1024px.
- Founder approval gates for Angle, Outline and final content.
- Sanitized operational history with safe JSON/Markdown export.
- Explicit evidence-authority recovery for bounded trusted hosts.
- Coverage Support fail-closed gate before Angle.
- Durable EvidenceSet checkpoint before Coverage Support:
  - fresh research evidence is approved with an exact reusable snapshot;
  - the locked EvidenceSet commits before Coverage Support;
  - an `insufficient_support` failure no longer deletes the canonical Evidence rows referenced by diagnostics;
  - crash/reclaim after the checkpoint reuses the EvidenceSet instead of repeating research.

## Verified release gates

- UI-UX-02: `PASS_UI_UX_02`
- UI-UX-03: `PASS_UI_UX_03`
- PR #427 exact-head GitHub CI: SUCCESS
- PR #427 merge tree: zero file differences from the verified candidate
- No auto-publish was added.
- No automatic retry was added.
- No generic `.edu` or broad authority trust was added.

## Important limitation

This release candidate does **not** claim `PASS_CONTENT_PRODUCTION_V1_RC1` yet.

The previous Q07 real pilot stopped at `insufficient_support`. The transaction-boundary defect found during that pilot is fixed here, but a **fresh Q07 case** still needs to run on this release candidate to prove the full real-content path:

Evidence → Coverage Support → Angle → Founder approval → Outline → Writer → Quality → Founder final approval.

Previous blocked Q07 cases remain immutable audit records and must not be retried.

## WordPress

ContentEngine still does **not** auto-publish.

The intended release flow remains:

approved ContentVersion / review package → Founder manually creates/reviews WordPress Draft → Founder publishes.

## Release baseline

Backend blocker merge before release metadata:

`f8bcdec3b0be9fa9ed7b3a036840543bba9a5fd8`

The GitHub Release tag points to the release-metadata merge commit, which contains no runtime behavior beyond this baseline except the release workflow/notes themselves.
