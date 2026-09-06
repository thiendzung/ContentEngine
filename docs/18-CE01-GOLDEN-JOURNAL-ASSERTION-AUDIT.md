# CE01 — GOLDEN JOURNAL — ASSERTION AUDIT V1

Status: **PASS FOR HUMAN EDITORIAL REVIEW**

Phase: `CE01 / PR-E — Walking Skeleton`

Task: `T01.41 — Add basic assertion audit`

Draft audited:

`docs/17-CE01-GOLDEN-JOURNAL-DRAFT-EN.md`

Inputs:

- EvidenceSet: `es_ce01_price_v1` — locked;
- OriginalityPack: `opack_ce01_price_v1` — approved;
- Artwork fact lock: `docs/16-CE01-ARTWORK-ANCHOR.md`;
- runtime artifact: `artifacts/runtime/ce01-artwork-anchor-20260906T025834Z.json`;
- Founder project clarification: the real MOTGU website currently has no real published Journal posts.

## Audit rule

Each important statement is classified as one of:

- `SUPPORTED_FACT` — mapped to locked evidence or runtime fact lock;
- `EDITORIAL_GUIDANCE` — MOTGU interpretation/position, not presented as external fact;
- `INTERNAL_SYSTEM_RULE` — implementation/editorial rule, not visible factual copy;
- `UNSUPPORTED` — must be removed, narrowed or researched before human approval.

Critical unsupported assertions must equal zero before T01.42.

---

## A01 — No single fixed formula for every artwork

Draft statement:

> There is no single fixed formula that explains every original painting.

Type: `SUPPORTED_FACT`

Support:

- `CLAIM-01`;
- `SRC-01` Smithsonian American Art Museum;
- `SRC-02` Sotheby’s specialist estimate guidance as corroboration.

Guard respected:

The Draft does not say art has no market value or that price is arbitrary.

Result: `PASS`.

---

## A02 — Factors specialists may consider

Draft statement scope:

- artist/maker;
- origin/documented history;
- date;
- materials;
- dimensions;
- rarity/type;
- subject;
- condition;
- comparable sales.

Type: `SUPPORTED_FACT`

Support:

- `CLAIM-02` → `SRC-02`.

Bias note:

Sotheby’s is a commercial auction house. The Draft correctly frames these as examples used in professional assessment, not a universal formula.

Result: `PASS`.

---

## A03 — Provenance meaning

Draft statement:

> Provenance ... means the documented ownership or collecting history of a work.

Type: `SUPPORTED_FACT`

Support:

- `CLAIM-03` → `SRC-03` Getty.

Guard respected:

The Draft does not claim every MOTGU work has provenance and does not invent provenance for the selected Artwork.

Result: `PASS`.

---

## A04 — Price is not a score for personal taste

Draft statements include:

> An artwork price is information, not a score.

and

> A higher price should not be a shortcut for your own judgement.

Type: `EDITORIAL_GUIDANCE`

Support/context:

- approved Angle A;
- approved calibration examples POS-01, POS-02, POS-04;
- ContentCase reader transformation;
- MOTGU brand position.

Audit note:

These are not presented as scientific or universal art-market facts. They are MOTGU’s reader guidance.

Result: `PASS`.

---

## A05 — Selected Artwork identity and stable facts

Draft statement scope:

- `Tranh đường tàu phố cổ Hà Nội`;
- Hoa Lê;
- year 2025;
- oil on canvas;
- 60 × 80 cm.

Type: `SUPPORTED_FACT`

Support:

- runtime-verified Artwork fact lock;
- canonical WordPress/WooCommerce/ACF record;
- `docs/16-CE01-ARTWORK-ANCHOR.md`.

Result: `PASS`.

---

## A06 — Dynamic Artwork price/status snapshot

Draft contains an **internal editorial snapshot**, not durable visible prose:

- price: `2,500,000 VND`;
- sale status: `available`;
- stock: `1`;
- location: `on-view`;
- read at `2026-09-06T02:58:34Z`.

Type: `SUPPORTED_FACT + INTERNAL_SYSTEM_RULE`

Support:

- runtime artifact `ce01-artwork-anchor-20260906T025834Z.json`;
- SHA-256 `1f7eda404a8c2c1d7367ccad23afea25c8553308c195b7c881341c6dbb2f771c`.

Guard:

The Draft explicitly says not to hard-code these values into durable prose and requires live render/re-read at publish time.

Result: `PASS`.

---

## A07 — WooCommerce/current Artwork page remains source for live commerce facts

Draft statement:

> For that second group, the current Artwork page should remain the source of truth. An old Journal paragraph should not become a second price list.

Type: `INTERNAL_SYSTEM_RULE / EDITORIAL_GUIDANCE`

Support:

- `CLAIM-04`;
- `SRC-04` MOTGU Product & Data Contract;
- WooCommerce owns price/stock/commerce state.

Result: `PASS`.

---

## A08 — Practical take-home costs may be separate

Draft statement scope:

- artwork price may not be the whole practical take-home cost;
- MOTGU shipping rules may include packaging, shipping and insurance;
- oversize works may require a quote.

Type: `SUPPORTED_FACT`

Support:

- `CLAIM-05` → `SRC-04` MOTGU Product & Data Contract.

Guard respected:

The Draft gives no fixed shipping amount, delivery time, customs/export promise or universal process.

Result: `PASS`.

---

## A09 — First-time buyer questions and decision guidance

Draft sections:

- five questions before deciding;
- “take your time” guidance;
- ask about a work without sales pressure.

Type: `EDITORIAL_GUIDANCE`

Support/context:

- approved calibration;
- ContentCase;
- OriginalityPack;
- selected Angle.

No external factual authority is implied.

Result: `PASS`.

---

## A10 — Real website has no published Journal Content Memory yet

Draft metadata states:

> The real MOTGU website is still being built and currently has no real published Journal posts.

Type: `INTERNAL_SYSTEM_RULE / FIRST-PARTY PROJECT STATE`

Source:

Founder clarification in the active CE01 review.

Visibility:

This is internal Draft metadata, not public article copy.

Important distinction:

Golden/demo WordPress content is test content and must not be treated as production Content Memory for CREATE/UPDATE/REFRESH or real internal-link decisions.

Result: `PASS`.

---

## A11 — “Different works can give different weight to those factors”

Draft wording:

> Different works can give different weight to those factors, so a list like this is context, not a calculator.

Type: `EDITORIAL_SYNTHESIS`

Audit:

The key factual basis is that specialist assessment is multi-factor and no universal formula is claimed. The sentence is used to prevent mechanical interpretation, not to introduce a new valuation formula.

Risk: `LOW`.

Required action: `NONE FOR CE01`; if future production requires sentence-level evidence strictness, rewrite more conservatively or map to a stronger source.

Result: `PASS / LOW-RISK SYNTHESIS`.

---

# Unsupported / contradiction scan

Critical unsupported assertions: `0`.

Critical contradicted assertions: `0`.

Invented artist intent: `0`.

Unsupported investment/appreciation claims: `0`.

Universal fair-price claims: `0`.

Fake scarcity/urgency: `0`.

Current dynamic commerce facts presented as durable copy: `0`.

Fake existing Journal links: `0`.

NeedHypothesis silently promoted from `PROPOSED`: `NO`.

## Source-copy check — CE01 basic

No long source quotation is used.

The Draft expresses the locked claim map in MOTGU’s own simple wording and keeps external-source names in a lightweight trust note.

Production-grade phrase-overlap/source-copy evaluation remains CE05/CE06 work; this CE01 audit does not claim to replace it.

## Assertion Audit verdict

`PASS FOR T01.42 HUMAN EDITORIAL REVIEW`

The Draft has zero critical unsupported assertions under the current locked EvidenceSet and runtime Artwork fact lock.

This does **not** mean the article is publishable yet. Founder human editorial review is still required for usefulness, MOTGU voice, generic/AI-like feel and overall direction.