# CQ-07 P01 Real Pilot Execution Input

Status: READY FOR FOUNDER EXECUTION AUTHORIZATION
Tracking: #233
Working PR: #238
Pair contract: `docs/CQ07_PILOT_CONTRACT.md`

This file freezes the exact Founder manual-intake payload for the real P01 pilot.
It is not an execution receipt and does not authorize production/publication.

## P01 identity

- ID: P01
- Role: `pillar`
- Canonical title: **Buying Your First Original Vietnamese Artwork: A Calm, Practical Guide**
- Source locale: `en`
- Required locales: `en`, `vi-VN`
- Research country: `vn`

## Customer problem

Reader:
A first-time buyer who likes Vietnamese art but does not consider themselves an art
expert or collector.

Situation:
They have encountered original Vietnamese artwork they may want to own, but do not yet
know how to judge the information in front of them or when they know enough to decide.

Need:
Reduce uncertainty about what the work is, who made it, what evidence to inspect, what
questions to ask, how to understand price transparency, and what remains uncertain before
purchase.

Primary question:
**How can a first-time buyer understand, evaluate and buy an original Vietnamese artwork
without needing to be an art expert?**

Primary intent:
`learn`

Promise:
Give a calm, practical, low-pressure decision path so a first-time buyer knows what to
check, what to ask and what remains uncertain before buying an original Vietnamese
artwork.

## Frozen coverage requirements

1. Explain original vs print/edition at overview depth and explicitly leave detailed
   verification depth to C02.
2. Explain the core artwork and artist information a first-time buyer should inspect
   before deciding.
3. Explain which questions reduce uncertainty about authorship, provenance and the exact
   work.
4. Explain price transparency without inventing one universal correct price for art.
5. Explain at overview level what signature, certificate and invoice can and cannot
   establish.
6. Give a low-pressure decision checklist and a clear next step to Artist / Artwork /
   Visit rather than pressure selling.

## Founder-owned originality input

Material:
MOTGU's editorial position is that a first-time art buyer should not need specialist
vocabulary or collector status to make a careful decision. The useful job of the guide is
to reduce uncertainty by making the exact artwork, artist, originality status, supporting
documents, price context and remaining unknowns visible. The reader should be able to
pause or ask for more information without sales pressure.

Writer use:
Use this only as MOTGU's first-party editorial perspective and tone. Build the article
around a calm decision process: understand the work, inspect the facts, ask focused
questions, identify uncertainty, then decide or pause. Keep C02's original-vs-print
verification depth delegated rather than duplicating it here.

Guardrails:
- Do not present this first-party perspective as external market/customer evidence.
- Do not invent artist biography, provenance, signatures, certificates, invoices, prices,
  policies, customer stories or artwork facts.
- Do not claim one visual cue or one COA alone proves authenticity.
- Do not define one universal correct price or budget for original art.
- Do not use investment-return framing.
- Do not expand into the separate P02 logistics pillar.
- Do not pressure the reader to buy.

## Exact manual-intake payload

```json
{
  "project_slug": "motgu",
  "source_locale": "en",
  "research_country": "vn",
  "required_locales": ["en", "vi-VN"],
  "content_role": "pillar",
  "reader": "A first-time buyer who likes Vietnamese art but does not consider themselves an art expert or collector.",
  "situation": "They have encountered original Vietnamese artwork they may want to own, but do not yet know how to judge the information in front of them or when they know enough to decide.",
  "need": "Reduce uncertainty about what the work is, who made it, what evidence to inspect, what questions to ask, how to understand price transparency, and what remains uncertain before purchase.",
  "question": "How can a first-time buyer understand, evaluate and buy an original Vietnamese artwork without needing to be an art expert?",
  "intent": "learn",
  "promise": "Give a calm, practical, low-pressure decision path so a first-time buyer knows what to check, what to ask and what remains uncertain before buying an original Vietnamese artwork.",
  "coverage_requirements": [
    "Explain original vs print/edition at overview depth and explicitly leave detailed verification depth to C02.",
    "Explain the core artwork and artist information a first-time buyer should inspect before deciding.",
    "Explain which questions reduce uncertainty about authorship, provenance and the exact work.",
    "Explain price transparency without inventing one universal correct price for art.",
    "Explain at overview level what signature, certificate and invoice can and cannot establish.",
    "Give a low-pressure decision checklist and a clear next step to Artist / Artwork / Visit rather than pressure selling."
  ],
  "selection_reason": "Founder selected P01 as the Pillar half of CQ-07 Option B to test whether a first-time-buyer guide can provide useful bounded breadth without consuming C02 originality-verification depth.",
  "originality_material": "MOTGU's editorial position is that a first-time art buyer should not need specialist vocabulary or collector status to make a careful decision. The useful job of the guide is to reduce uncertainty by making the exact artwork, artist, originality status, supporting documents, price context and remaining unknowns visible. The reader should be able to pause or ask for more information without sales pressure.",
  "originality_writer_use": "Use this only as MOTGU's first-party editorial perspective and tone. Build the article around a calm decision process: understand the work, inspect the facts, ask focused questions, identify uncertainty, then decide or pause. Keep C02's original-vs-print verification depth delegated rather than duplicating it here.",
  "originality_guardrails": "Do not present this first-party perspective as external evidence. Do not invent artist/artwork/provenance/document/price/policy facts. Do not claim one visual cue or one COA proves authenticity. Do not define one universal correct price. Do not use investment-return framing. Do not expand into P02 logistics. Do not pressure the reader to buy.",
  "idempotency_key": "cq07-p01-real-pilot-v1"
}
```

## Execution boundary

The next real step may use the existing bounded research/model pipeline only after Founder
authorization for those external/model calls. The run must stop at every existing human
Angle, Outline and final-review gate. No production DB, publication, WordPress/Rank Math
mutation or operational migration is authorized.
