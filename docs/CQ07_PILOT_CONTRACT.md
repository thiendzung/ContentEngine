# CQ-07 Pilot Contract — P01 + C02

Status: FROZEN FOR PILOT
Founder decision: Option B
Tracking: #233
Clean baseline source: main after PR #241
Historical working PR #238: superseded / evidence only

## Source precedence

Use `MOTGU-VALUE-PROPOSITION-KEYWORD-CONTENT-SYSTEM-v1.0` for the canonical
Content Master Plan identity, content type, audience scope and priority.

Use `MOTGU_DEEP_RESEARCH_04_DATA_LOCK` and the Search Language / Question Map
for the underlying first-time-buyer problem, trust questions and wording guardrails.

The older Data Lock narrows the first-artwork opportunity more strongly to Hanoi and
contains logistics material. The later v1.0 Master Plan separates logistics into P02.
For this pilot, P01 must not silently absorb P02 logistics depth or C02 verification depth.

## Pair identity

### P01 — Pillar

- Canonical title: **Buying Your First Original Vietnamese Artwork: A Calm, Practical Guide**
- Role: `pillar`
- Audience scope: Local + Global
- Priority: A1
- Master-plan medicines: P01 / P02 / P03
- Source locale: `en`
- Required locales: `en`, `vi-VN`
- Research country: `vn`

Customer problem:
A first-time buyer likes original Vietnamese art but lacks confidence about what is
original, what information to check, what questions to ask, how to understand price,
and when there is enough information to decide.

Frozen primary question:
**How can a first-time buyer understand, evaluate and buy an original Vietnamese artwork
without needing to be an art expert?**

Frozen primary intent:
`learn`

Frozen promise:
Give a calm, practical, low-pressure decision path so a first-time buyer knows what to
check, what to ask and what remains uncertain before buying an original Vietnamese
artwork.

Frozen coverage requirements:
1. Explain original vs print/edition at overview depth and explicitly leave detailed
   verification depth to C02.
2. Explain the core artwork and artist information a first-time buyer should inspect
   before deciding.
3. Explain which questions reduce uncertainty about authorship, provenance and the
   exact work.
4. Explain price transparency without inventing one universal correct price for art.
5. Explain at overview level what signature, certificate and invoice can and cannot
   establish.
6. Give a low-pressure decision checklist and a clear next step to Artist / Artwork /
   Visit rather than pressure selling.

Pillar boundary:
P01 is navigation + bounded synthesis. It must not reproduce the full C02 verification
guide, and it must not expand into the separate P02 logistics pillar.

### C02 — Cluster

- Canonical title: **Original or Print? How to Know What You Are Buying**
- Role: `cluster`
- Audience scope: Both
- Priority: A1
- Master-plan medicines: P01 / P02
- Source locale: `en`
- Required locales: `en`, `vi-VN`
- Research country: `vn`

Customer problem:
A new buyer sees original works, editions, prints and souvenir-like objects and does not
know what evidence is sufficient to understand what is actually being sold.

Frozen primary question:
**How do I know whether a Vietnamese artwork is an original, an edition or a print?**

Frozen primary intent:
`evaluate`

Frozen promise:
Explain unique/original, edition and print distinctions and show the buyer which artwork
facts and documents to cross-check before purchase, without pretending that one visual
cue or one certificate proves everything.

Frozen coverage requirements:
1. Define original/unique work, edition and print/reproduction in buyer-facing language.
2. Explain how material, medium, process and exact artwork fields help identify what is
   being sold without treating appearance alone as proof.
3. Explain what a signature can and cannot establish.
4. Explain what a certificate, invoice and provenance record can and cannot establish.
5. Give a concrete cross-check checklist for the exact artwork before purchase.
6. Distinguish originality/authorship evidence from subjective artistic quality or
   investment value.
7. End with the exact Artwork record as the next verification surface.

Cluster boundary:
C02 must solve this one trust problem in materially greater depth than P01. It must not
widen into a general first-time-buyer guide or repeat P01 synthesis as filler.

## Known relationship for this pilot

The Founder selected C02 as the related Cluster for P01. This is an editorial pilot
relationship, not authorization to create a generalized database relationship.

Do not add a Pillar↔Cluster table or new durable relation until the completed pilot proves
a concrete identity/query/update need that the existing model cannot represent.

## Pair-level acceptance

The pair passes CQ-07 only if:
- P01 remains useful without consuming C02 depth;
- C02 is materially deeper on the originality/print decision;
- repeated material is intentional and bounded;
- internal-link intent is truthful and useful;
- VI and EN lanes independently pass the existing quality gates;
- Founder can compare exact immutable artifacts and approvals;
- the pilot records whether the existing identity model is sufficient.

## Boundaries

No auto-publish, WordPress/Rank Math mutation, operational DB migration, production
activation or generalized Pillar↔Cluster schema is authorized by this contract.
