# CQ-07 C02 Real Pilot Execution Input

Status: AWAITING FOUNDER EXTERNAL/MODEL EXECUTION AUTHORIZATION
Tracking: #303
Pair contract: `docs/CQ07_PILOT_CONTRACT.md`

This file freezes the exact Founder manual-intake payload for the real C02 pilot.
It is not an execution receipt and does not authorize provider/model calls, production
activation or publication.

## C02 identity

- ID: C02
- Role: `cluster`
- Canonical title: **Original or Print? How to Know What You Are Buying**
- Source locale: `en`
- Required locales: `en`, `vi-VN`
- Research country: `vn`

## Customer problem

Reader:
A first-time buyer who is comparing Vietnamese artworks and wants to understand whether
the exact item being offered is a unique/original work, an edition, or a print/reproduction
without needing specialist authentication expertise.

Situation:
They are looking at an artwork or listing described with terms such as original, edition
or print, but are unsure which object-level facts, process details and documents are
sufficient to understand what is actually being sold. In plain buyer language, the fear is:
**“Is the artwork I am about to buy really an original work, or am I actually buying a
print/copy/reproduction?”**

Need:
Reduce uncertainty by distinguishing unique/original work, edition and print/reproduction,
then cross-checking the exact artwork's material, medium, process, authorship/originality
information, signature, certificate, invoice and provenance record while keeping unknowns
explicit.

Primary question:
**How do I know whether a Vietnamese artwork is an original, an edition or a print?**

Primary intent:
`evaluate`

Promise:
Explain unique/original, edition and print distinctions and show the buyer which artwork
facts and documents to cross-check before purchase, without pretending that one visual cue
or one certificate proves everything.

## Frozen coverage requirements

1. Define original/unique work, edition and print/reproduction in buyer-facing language.
2. Explain how material, medium, process and exact artwork fields help identify what is
   being sold without treating appearance alone as proof.
3. Explain what a signature can and cannot establish.
4. Explain what a certificate, invoice and provenance record can and cannot establish.
5. Give a concrete cross-check checklist for the exact artwork before purchase.
6. Distinguish originality/authorship evidence from subjective artistic quality or
   investment value.
7. End with the exact Artwork record as the next verification surface.

## Cluster boundary

C02 must solve this one trust problem in materially greater depth than P01. It must not
widen into a general first-time-buyer guide or repeat P01 synthesis as filler.

The reader-language framing above does not replace the canonical question. It is a Writer
framing instruction so the article answers the buyer's real fear in plain language rather
than reading like an academic authentication guide.

## Founder-owned originality input

Material:
MOTGU's editorial position for this pilot is that a buyer should understand the exact
object being offered rather than rely on a single visual cue, signature, certificate or
sales label. A careful decision comes from cross-checking the artwork's material, medium,
process, artist/work identity, edition status where relevant, supporting documents and
provenance information, while keeping any remaining uncertainty visible.

Writer use:
Use this only as MOTGU's first-party editorial perspective and verification framing.
Build C02 around a concrete object-level cross-check: identify what category of object is
being sold, inspect the exact artwork facts, compare those facts with
signature/document/provenance information, identify inconsistencies or unknowns, then
decide whether the description is sufficiently clear. Keep the article materially narrower
and deeper than P01 rather than turning it into another general buying guide. Prefer plain
buyer language such as “Is this really an original work, or am I buying a print/copy?”
over technical authentication jargon when both express the same supported meaning.

Guardrails:
- Do not present MOTGU's editorial framing as external market/customer evidence.
- Do not invent artist biography, artwork history, provenance, edition size, signatures,
  certificates, invoices, ownership records or seller claims.
- Do not treat visual appearance, a signature, a certificate or an invoice alone as
  conclusive proof of authorship or originality.
- Do not imply that originality determines artistic quality or investment value.
- Do not widen into P01's general buying process or P02 logistics.
- Do not pressure the reader to buy.

## Exact manual-intake payload

```json
{
  "project_slug": "motgu",
  "source_locale": "en",
  "research_country": "vn",
  "required_locales": ["en", "vi-VN"],
  "content_role": "cluster",
  "reader": "A first-time buyer who is comparing Vietnamese artworks and wants to understand whether the exact item being offered is a unique/original work, an edition, or a print/reproduction without needing specialist authentication expertise.",
  "situation": "They are looking at an artwork or listing described with terms such as original, edition or print, but are unsure which object-level facts, process details and documents are sufficient to understand what is actually being sold. In plain buyer language, the fear is: Is the artwork I am about to buy really an original work, or am I actually buying a print/copy/reproduction?",
  "need": "Reduce uncertainty by distinguishing unique/original work, edition and print/reproduction, then cross-checking the exact artwork's material, medium, process, authorship/originality information, signature, certificate, invoice and provenance record while keeping unknowns explicit.",
  "question": "How do I know whether a Vietnamese artwork is an original, an edition or a print?",
  "intent": "evaluate",
  "promise": "Explain unique/original, edition and print distinctions and show the buyer which artwork facts and documents to cross-check before purchase, without pretending that one visual cue or one certificate proves everything.",
  "coverage_requirements": [
    "Define original/unique work, edition and print/reproduction in buyer-facing language.",
    "Explain how material, medium, process and exact artwork fields help identify what is being sold without treating appearance alone as proof.",
    "Explain what a signature can and cannot establish.",
    "Explain what a certificate, invoice and provenance record can and cannot establish.",
    "Give a concrete cross-check checklist for the exact artwork before purchase.",
    "Distinguish originality/authorship evidence from subjective artistic quality or investment value.",
    "End with the exact Artwork record as the next verification surface."
  ],
  "selection_reason": "Founder selected C02 as the Cluster half of CQ-07 Option B to test whether one narrower trust problem—original versus edition versus print—can be solved in materially greater verification depth without duplicating P01's broader first-time-buyer decision guide.",
  "originality_material": "MOTGU's editorial position for this pilot is that a buyer should understand the exact object being offered rather than rely on a single visual cue, signature, certificate or sales label. A careful decision comes from cross-checking the artwork's material, medium, process, artist/work identity, edition status where relevant, supporting documents and provenance information, while keeping any remaining uncertainty visible.",
  "originality_writer_use": "Use this only as MOTGU's first-party editorial perspective and verification framing. Build C02 around a concrete object-level cross-check: identify what category of object is being sold, inspect the exact artwork facts, compare those facts with signature/document/provenance information, identify inconsistencies or unknowns, then decide whether the description is sufficiently clear. Keep the article materially narrower and deeper than P01 rather than turning it into another general buying guide. Prefer plain buyer language such as ‘Is this really an original work, or am I buying a print/copy?’ over technical authentication jargon when both express the same supported meaning.",
  "originality_guardrails": "Do not present MOTGU's editorial framing as external market/customer evidence. Do not invent artist biography, artwork history, provenance, edition size, signatures, certificates, invoices, ownership records or seller claims. Do not treat visual appearance, a signature, a certificate or an invoice alone as conclusive proof of authorship or originality. Do not imply that originality determines artistic quality or investment value. Do not widen into P01's general buying process or P02 logistics. Do not pressure the reader to buy.",
  "idempotency_key": "cq07-c02-real-pilot-v1"
}
```

## Execution boundary

The next real step may create this intake only after a separate explicit Founder
authorization. External research/model calls require a separate explicit Founder
authorization. Once execution is authorized, the run must stop at every existing Angle,
Outline and final-review human gate.

No publication, WordPress/Rank Math mutation, generalized Pillar↔Cluster schema change or
unbounded workflow execution is authorized by this file.
