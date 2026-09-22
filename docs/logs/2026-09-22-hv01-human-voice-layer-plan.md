# HV-01 — Human Voice Layer isolated implementation plan

Date: 2026-09-22  
Status: IMPLEMENTATION / ISOLATED LEGO / DO NOT MERGE YET  
Tracking: #185

## Goal

Add a small reusable Human Voice layer that can make Journal prose less formulaic and
more grounded in real artist/studio/artwork detail without inventing facts.

This slice is deliberately parked outside the active Journal pipeline. It is safe to
develop in parallel and integrate later after the current main-line work closes.

## Problem boundary

Existing ContentEngine already owns Brand/Language DNA, Review/Revise, Assertion Audit,
Source-copy, Reader Value, SEO/AI Readiness and Founder final review.

HV-01 does **not** attempt to detect whether text was written by AI and does not try to
defeat AI detectors. Its job is narrower:

1. identify deterministic formulaic style markers;
2. give a rewrite model only approved source/evidence boundaries;
3. require exact claim/evidence references in output;
4. reject new factual claims, numbers or quoted speech;
5. return style findings before/after for later quality review.

## Architecture

```text
immutable revised draft
        |
        v
[future] assertion/truth boundary
        |
        v
HumanVoiceInput
  - exact segments
  - allowed claim refs
  - allowed evidence refs
  - grounded texture evidence
        |
        v
HumanVoiceModelPort
  bounded structured rewrite only
        |
        v
deterministic No-New-Fact guard
  - segment identity/order
  - claim boundary
  - evidence boundary
  - new_factual_claims == []
  - numeric guard
  - quote guard
        |
        v
HumanVoiceRewriteResult
        |
        v
[future] re-audit + Reader Value / final quality
        |
        v
Founder final review
```

The future re-audit after rewriting is intentional. A style rewrite must never inherit
the factual safety verdict of different bytes.

## Work checklist

### HV-01A — Grounded texture contract
- [x] Evidence kinds: artist quote, studio observation, material/process, artwork detail,
      place detail, personal vocabulary.
- [x] Stable evidence ID + source ref + exact text.
- [x] Segment-level allowed claim refs.
- [x] Segment-level allowed evidence refs.
- [x] Explicit forbidden-invention list.

### HV-01B — Formulaic style markers
- [x] Deterministic Vietnamese and English marker scan.
- [x] Common formula patterns are advisory findings only.
- [x] Repeated paragraph transition marker.
- [x] No AI-authorship label or probability.

### HV-01C — Structured rewrite contract
- [x] Provider-agnostic `HumanVoiceModelPort`.
- [x] Bounded model input bundle.
- [x] Exact segment identity/order.
- [x] Explicit claim refs and evidence refs in output.
- [x] Explicit `new_factual_claims` field.

### HV-01D — No-New-Fact guard
- [x] Unknown claim ref fails closed.
- [x] Unknown/out-of-scope evidence ref fails closed.
- [x] Non-empty `new_factual_claims` fails closed.
- [x] Newly introduced numeric token fails unless present in source/cited evidence.
- [x] Newly introduced quoted speech fails unless present in source/cited evidence.

### HV-01E — Bounded execution
- [x] 1–3 validation attempts.
- [x] Retry only malformed/unsafe structured output.
- [x] No DB write.
- [x] No workflow activation.
- [x] No provider/model routing.
- [x] No external side effect.

### HV-01F — Focused regression
- [x] Grounded rewrite PASS.
- [x] Unknown evidence FAIL.
- [x] Unknown claim FAIL.
- [x] New claim FAIL.
- [x] New number FAIL.
- [x] Invented quote FAIL.
- [x] Segment order drift FAIL.
- [x] Invalid first response may retry and then PASS.
- [x] Style scan is not authorship detection.
- [ ] Exact-head CI PASS.
- [ ] OpenCodeReview exact-ref review.
- [ ] Agent Local bounded local proof if MG requests it.

### HV-01G — Future integration (not in this PR)
- [ ] Define canonical artifact type + immutable lineage for Human Voice output.
- [ ] Bind exact pre-rewrite assertion/truth verdict.
- [ ] Integrate after factual review, not before it.
- [ ] Re-run Assertion Audit/Truth Boundary on rewritten bytes.
- [ ] Feed exact rewritten bytes into Reader Value / Search-AI readiness.
- [ ] Preserve all warnings for Founder final review.
- [ ] Add operator/UI status only after backend contract is accepted.

## Non-goals

- AI-detector evasion.
- Randomness, deliberate mistakes or fake human quirks.
- Invented artist intention, memory, motive, dialogue or sensory detail.
- New prompt/provider/model policy.
- Database migration.
- Active Journal pipeline modification.
- Operational database change.
- Publication.
- Removal of human approval gates.

## Integration decision later

Recommended future order:

```text
Writer
-> Review/Revise
-> Assertion Audit + Truth Boundary
-> Human Voice rewrite
-> No-New-Fact validation
-> Assertion Audit + Truth Boundary again on exact rewritten bytes
-> Source-copy / Reader Value / SEO-AI readiness as applicable
-> Founder final review
```

Before integration, re-check this ordering against the then-current canonical quality
pipeline. HV-01 itself intentionally makes no active workflow change.
