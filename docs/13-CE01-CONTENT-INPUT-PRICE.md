# CE01 — CONTENT INPUT — PRICE

Status: **APPROVED / GATE D PASS**

Phase: `CE01 / PR-D — Content Input`

Selected ContentOpportunity:

- topic: `price`;
- opportunity ID: `opp_ea484183ba36c6b2`;
- NeedHypothesis: `need_fc6259977d637e6f`;
- ContentExperiment draft: `exp_cdc69b59a413393c`;
- NeedHypothesis status: `PROPOSED`.

This document is the manual CE01 input pack allowed by `docs/08-JOURNAL-SPEC.md`.
It does not create CE02 persistence/database models.

The selected opportunity is worth developing, but it is not proven customer truth.
Founder approved the calibration and content direction on `2026-09-06`. The current narrow EvidenceSet and OriginalityPack are locked for CE01 Phase E input. Proceed to Angle; do not skip Angle/Outline approval or expand into unsupported pricing claims.

---

## 1. Working direction

Do **not** start with a generic article such as:

> Why is art expensive?

For CE01, use a narrower first-time-buyer question:

> **What actually affects the price of an original painting, and what should a first-time buyer compare before deciding?**

MOTGU should not claim to provide a universal formula for art prices.
The useful job is to make an opaque number easier to understand, separate facts from taste, and give the reader a calm set of questions to use with a real work.

Working reader promise:

> You do not need to understand the whole art market to make a first decision. Learn which facts can affect market value, which facts are specific to the work in front of you, what extra costs may exist, and what questions to ask before buying.

---

# D1 — EDITORIAL CALIBRATION

## 2. Positive calibration examples — APPROVED

These examples are built from the approved MOTGU direction: warm, curious, personal, quiet, thoughtful, unhurried; low-pressure CTA; no luxury/scarcity language.

Founder approved them for the CE01 English calibration pack on `2026-09-06`.

### POS-01 — opening

**Locale:** `en`

**Type:** opening

**Status:** `FOUNDER_APPROVED`

> An art price can feel like a number with no map. It does not have to. Start with the work in front of you: what it is, who made it, its size, material and history. Then ask the simpler question: do you want to keep looking at it?

Why this fits:

- acknowledges uncertainty without making the reader feel inexperienced;
- concrete before poetic;
- calm rhythm;
- no sales pressure;
- moves from market confusion back to the actual work.

### POS-02 — direct answer

**Locale:** `en`

**Type:** direct_answer

**Status:** `FOUNDER_APPROVED`

> There is no single formula that makes a painting “worth it” for you. Market value can depend on several concrete factors; your decision also has a personal part. We can explain the facts around a work. You decide whether the work matters enough to bring home.

Why this fits:

- answer-first;
- separates market facts from personal choice;
- avoids pretending taste can be scored;
- positions MOTGU as a guide, not a closer.

### POS-03 — MOTGU connection / CTA

**Locale:** `en`

**Type:** CTA

**Status:** `FOUNDER_APPROVED`

> If one painting keeps pulling you back, ask about it. Nothing formal. We can show you the work’s current price, size, material, availability and what bringing it home would involve.

Why this fits:

- uses the approved “Nothing formal / Ask anything” direction;
- concrete next step;
- no urgency or fake scarcity;
- naturally connects Journal → Artwork / Inquiry / Visit.

### POS-04 — first-buyer reassurance

**Locale:** `en`

**Type:** editorial_voice

**Status:** `FOUNDER_APPROVED`

> Take your time. A good first purchase does not need to prove that you understand art. It needs to be a work you understand well enough to choose without being pushed.

Why this fits:

- simple language;
- low pressure;
- consistent with MOTGU’s unhurried artist-house position;
- useful emotional direction without hype.

## 3. Negative calibration examples — APPROVED

These are explicit examples of language the engine must reject.
Founder approved them as negative calibration examples on `2026-09-06`.

### NEG-01 — investment promise / scarcity

**Status:** `FOUNDER_APPROVED_NEGATIVE`

> Invest in this timeless masterpiece now before prices rise and the opportunity disappears.

Reject because:

- unsupported investment promise;
- fake urgency/scarcity;
- sales pressure;
- not MOTGU voice.

### NEG-02 — luxury hype

**Status:** `FOUNDER_APPROVED_NEGATIVE`

> This exclusive luxury artwork is a must-have statement piece for discerning collectors.

Reject because:

- generic luxury language;
- “must-have” pressure;
- says nothing useful about the work;
- sounds like commodity advertising.

### NEG-03 — invented artist intent

**Status:** `FOUNDER_APPROVED_NEGATIVE`

> The artist painted this work to express the loneliness of modern Hanoi life.

Reject unless an approved artist source supports that exact intent.

### NEG-04 — fake pricing formula

**Status:** `FOUNDER_APPROVED_NEGATIVE`

> Art pricing is simple: size × hours worked × artist reputation = the correct price.

Reject because:

- presents a false universal formula;
- hides uncertainty and market context;
- cannot be supported by the current EvidenceSet.

## 4. Short human editorial review form — APPROVED FOR CE01

Use this form for the CE01 Golden Journal:

1. `publishable_direction`: `yes | no`
2. `factual_issue`: `yes | no`
3. `feels_like_motgu`: `1–5`
4. `useful_to_target_reader`: `1–5`
5. `reader_state_improved`: `1–5`
6. `generic_or_ai_like`: `1–5` — lower is better
7. `source_copy_concern`: `yes | no`
8. `biggest_issue`: free text
9. `required_edit`: optional free text
10. `verdict`: `PUBLISHABLE_DIRECTION | NEEDS_CHANGES | REJECT_DIRECTION`

This form does not replace Assertion Audit or factual hard gates.

---

# D2 — CONTENT CASE

## 5. Manual AudienceHypothesis reference

CE01 does not persist the full CE02 audience model. This manual reference exists only so the ContentCase is traceable.

- ID: `aud_ce01_intl_first_time_art_buyer_001`
- Context: international traveller or visitor in/around Hanoi who is art-curious and may be considering a first original artwork purchase;
- knowledge level: beginner to moderate;
- stage: evaluating / first-time buyer;
- evidence status: `HYPOTHESIS`;
- confidence: `LOW_TO_MEDIUM`;
- source: founder-proposed audience scope + CE01 search signals;
- guard: do not describe this audience as verified MOTGU customer truth.

## 6. ContentCase — manual CE01

- ID: `cc_ce01_price_001`
- project: `motgu`
- content type: `journal`
- audience hypothesis ID: `aud_ce01_intl_first_time_art_buyer_001`
- NeedHypothesis ID: `need_fc6259977d637e6f`
- ContentOpportunity ID: `opp_ea484183ba36c6b2`
- ContentExperiment ID: `exp_cdc69b59a413393c`
- status: `APPROVED_FOR_CE01`

### Audience

International first-time or early-stage art buyer visiting or preparing to visit Hanoi; interested in original art but unsure how to interpret price and afraid of making an uninformed decision.

### Problem / desire

The reader can see a number attached to a painting but lacks a simple way to understand what can influence market value, what facts belong to the specific work, and what to compare before deciding.

The reader wants enough clarity to ask sensible questions and make a personal decision without pretending to be an expert.

### Primary question

> What actually affects the price of an original painting, and what should a first-time buyer compare before deciding?

### Desired action

Primary:

- inspect a specific Artwork with better questions and better context.

Natural next actions:

- open a relevant MOTGU Artwork;
- ask MOTGU about a specific work;
- visit and see a work in person when practical.

No forced sales CTA.

### Content hypothesis

If a first-time buyer receives a simple explanation of the concrete factors professionals use when assessing art, plus MOTGU-specific facts about a real physical work and the practical costs around taking it home, the reader will feel less intimidated and will be more able to evaluate a specific artwork rather than treating price as an unexplained signal of quality.

This is an experiment hypothesis, not a proven outcome.

### Originality statement

MOTGU should **not** compete with generic “why art is expensive” articles.

The MOTGU-specific value is:

1. anchor the explanation in the physical work the visitor can actually see;
2. expose concrete live facts such as dimensions, material, current price and availability from the canonical product record;
3. separate artwork price from practical delivery/shipping considerations;
4. explain what MOTGU can verify about the work and what remains personal judgement;
5. use a calm, low-pressure artist-house voice instead of investment/luxury framing.

### Reader before

> “I like the painting, but I do not understand why it costs this amount or whether I am making a foolish first purchase.”

### Reader after

> “I know which facts to look at, which questions to ask, what the price does and does not tell me, and I can decide whether this particular work matters enough to me.”

### Hard boundaries

Do not claim:

- art is a reliable investment;
- MOTGU prices are objectively cheap/fair/better than galleries;
- a higher price means a better artwork;
- a universal formula determines an artwork’s correct price;
- artist intention without approved artist evidence;
- current price or availability from memory;
- a certificate/provenance exists for every MOTGU work;
- scarcity or urgency unless canonical live data supports the exact claim and the wording is non-manipulative.

---

## 7. LocaleVariant — English

- ID: `lv_ce01_price_en_001`
- ContentCase ID: `cc_ce01_price_001`
- locale: `en`
- status: `APPROVED_FOR_CE01`
- content role: `cluster`
- primary intent: `evaluate`
- secondary intent: `trust`
- primary query: `price of art`

### Primary question

> What actually affects the price of an original painting, and what should a first-time buyer compare before deciding?

### Title direction

Preferred direction:

> **How to understand the price of an original painting: a first-time buyer’s guide**

Alternative for later angle review:

> **What are you actually paying for when you buy an original painting?**

Neither title is final before Angle approval.

### Keyword / query notes

Use search language as orientation, not density targets:

- price of art;
- art prices;
- how is art priced;
- what affects the price of a painting;
- first time buying art.

Do not force exact-match repetition.

### Reader transformation

- primary emotion: `uncertainty → clarity`;
- secondary: `intimidation → confidence`;
- arc: `uncertainty → orientation → concrete questions → personal confidence`.

### Must include

- direct answer early;
- no single fixed formula;
- concrete valuation factors supported by EvidenceSet;
- distinction between market/value factors and personal preference;
- provenance/condition only with careful wording;
- one MOTGU-specific section grounded in canonical product/commerce facts;
- practical note that shipping/delivery may be separate from artwork price;
- useful questions a first-time buyer can ask;
- low-pressure next step to a relevant Artwork / Visit / Inquiry.

### Must not claim

- guaranteed appreciation;
- “investment-grade”;
- universal fair price;
- exact pricing methodology of MOTGU/artist unless founder/artist provides it;
- exact current product price/stock without live canonical read at drafting time;
- invented artist intent;
- hidden-gem / must-do / exclusive / prestigious / luxury framing.

### Language / voice notes

- simple to moderate English;
- answer-first when possible;
- short/light paragraphs;
- warm, curious, personal;
- quiet, thoughtful, unhurried;
- low rhetorical-question frequency;
- grounded metaphor only;
- CTA invitational, never urgent.

---

# D3 — MANUAL EVIDENCE SET

## 8. EvidenceSet — LOCKED FOR CE01

- ID: `es_ce01_price_v1`
- ContentCase ID: `cc_ce01_price_001`
- version: `1`
- status: `LOCKED_FOR_CE01`
- locked: `YES`
- locked by: `founder`
- locked at: `2026-09-06`
- source review: `REVERIFIED_BEFORE_LOCK`

The set is intentionally small. Discovery sources from PR-B are not automatically promoted into factual evidence. If evidence or claim scope changes after this lock, create a new CE01 EvidenceSet version rather than silently changing v1.

## 9. Sources

### SRC-01 — Smithsonian American Art Museum

URL:

`https://americanart.si.edu/research/my-art/object-worth`

Source type: museum educational guidance.

Authority: `HIGH` for the bounded claim that fixed values are difficult and value/price depends on multiple factors.

Commercial bias: `LOW`.

Reviewed claim support:

- fixed values for artworks are difficult to establish;
- condition, interests of seller/purchaser and market trends can affect amounts asked/offered.

Intended use: `EVIDENCE`.

### SRC-02 — Sotheby’s specialist estimate guidance

URL:

`https://help.sothebys.com/en/support/solutions/articles/44002297435-how-are-estimates-determined-`

Source type: auction-house specialist guidance.

Authority: `MEDIUM_HIGH` for describing factors its specialists consider; not universal authority for all pricing.

Commercial bias: `HIGH`.

Reviewed claim support:

- specialist assessment can consider artist/maker, origin, provenance, date, materials, dimensions, rarity, subject/type and condition;
- comparable sales and performance of same/similar artists are also considered.

Intended use: `EVIDENCE_WITH_BIAS_NOTE`.

### SRC-03 — Getty / Categories for the Description of Works of Art

URL:

`https://www.getty.edu/publications/categories-description-works-art/categories/object-architecture-group/23/`

Source type: museum/research standards guidance.

Authority: `HIGH` for provenance definition and bounded role.

Commercial bias: `LOW`.

Reviewed claim support:

- provenance is ownership/collecting history;
- clear provenance may help establish authorship/authenticity and can affect a work’s interest/value.

Intended use: `EVIDENCE`.

### SRC-04 — MOTGU Product & Data Contract

Repository:

`thiendzung/MotguOS`

Path:

`docs/01-product-data-contract.md`

Source type: approved first-party MOTGU product/operations contract.

Authority: `CANONICAL_MOTGU` for the bounded product/commerce facts below.

Reviewed claim support:

- WooCommerce is canonical owner of price, stock, payment, deposit, shipping and orders;
- each physical work has its own SKU/image/dimensions and stock max 1;
- price is required when a work is for sale;
- sale status and physical location are separate;
- shipping may include packaging, shipping and insurance;
- oversize works may require a shipping quote;
- provenance/certificate is optional and public only when approved.

Intended use: `EVIDENCE + ORIGINALITY`.

## 10. Critical claim map

### CLAIM-01

Claim:

> There is no single fixed value formula that works for every artwork.

Support:

- `SRC-01` primary bounded support;
- `SRC-02` corroborates multi-factor professional assessment.

Allowed wording:

- “There is no single fixed formula for every artwork.”

Do not overstate as:

- “Art has no objective market value.”

### CLAIM-02

Claim:

> Professional valuation can consider several concrete factors, including the artist, provenance, materials, dimensions, rarity, subject/type, condition and comparable sales.

Support:

- `SRC-02`.

Guard:

Attribute this as examples of factors used by specialists, not a universal exhaustive formula.

### CLAIM-03

Claim:

> Provenance is the ownership history of a work and can contribute to authentication/context/value assessment.

Support:

- `SRC-03`;
- optional corroboration from `SRC-02`.

Guard:

Do not imply every MOTGU work has a long documented provenance.

### CLAIM-04

Claim:

> MOTGU’s current public price/availability must come from the canonical product/commerce record, not editorial memory.

Support:

- `SRC-04`.

Public-writing translation:

- use live product facts when referring to a specific work;
- do not explain WooCommerce implementation to the reader unless relevant.

### CLAIM-05

Claim:

> The artwork price and the practical cost of getting a work home may be separate; MOTGU shipping rules can include packaging, shipping and insurance, and oversize works may require a quote.

Support:

- `SRC-04`.

Guard:

Verify live policy/config before final publish if operational rules have changed.

## 11. Claims explicitly outside EvidenceSet v1

Do not write as fact without more evidence:

- MOTGU/artist exact base-pricing formula;
- how much artist reputation contributes to a specific MOTGU work;
- future resale value or investment return;
- claim that a specific MOTGU price is below/above market;
- claim that size has a linear relationship with price;
- claim that time spent making the work determines price;
- claim that all original art gets more valuable over time.

If the Angle needs one of these, route back to Evidence Research or founder/artist source.

---

# D4 — MANUAL ORIGINALITY PACK

## 12. OriginalityPack — APPROVED FOR CE01

- ID: `opack_ce01_price_v1`
- ContentCase ID: `cc_ce01_price_001`
- status: `APPROVED_FOR_CE01`
- approved by: `founder`
- approved at: `2026-09-06`

### ORIG-01 — live physical-work facts

Source: `SRC-04` canonical MOTGU contract.

MOTGU-specific material:

- the content can anchor abstract price discussion in a real physical Artwork with live price, dimensions, material, sale status and specific work identity;
- current commerce facts must be read from canonical data rather than remembered/editorial copies.

Writer use:

- “Here is what to look at on the actual work in front of you.”

Do not expose internal implementation details unnecessarily.

### ORIG-02 — price is not the whole take-home cost

Source: `SRC-04` canonical MOTGU contract.

MOTGU-specific material:

- packaging/shipping/insurance can be operationally separate from artwork price;
- oversize may require a quote.

Writer use:

- practical first-buyer checklist before deciding.

### ORIG-03 — no fake scarcity from status/location

Source: `SRC-04` canonical MOTGU contract + MOTGU brand boundary.

MOTGU-specific material:

- sale status and physical location are separate facts;
- availability should come from canonical state;
- editorial copy must not turn a status into manipulative urgency.

Writer use:

- explain availability plainly; do not create pressure.

### ORIG-04 — artist-house buying posture

Source: founder-approved MOTGU project direction + founder approval of this CE01 calibration pack on `2026-09-06`.

MOTGU-specific material:

- calm, personal, low-pressure guidance;
- “Take your time”, “Ask anything”, “Nothing formal”;
- artwork remains the centre of gravity rather than investment status or luxury signaling.

Writer use:

- the reader should leave with better questions and more confidence, not a feeling of having been sold to.

## 13. Originality gap still open

The pack does **not** contain an approved founder/artist explanation of how MOTGU sets the base price of a particular work.

This is not required while the approved direction stays with:

> how a first-time buyer can understand and evaluate a displayed price.

It **is required** if a later Angle changes to:

> how MOTGU prices its art / why this specific MOTGU work costs X.

Do not silently cross that boundary. A changed scope requires new evidence and human review.

---

# 14. GATE D — PASS

Founder decision on `2026-09-06`:

`APPROVE CALIBRATION + CONTENT DIRECTION`

Locked state:

- ContentCase clear: `YES — APPROVED_FOR_CE01`;
- LocaleVariant clear: `YES — APPROVED_FOR_CE01`;
- EvidenceSet sufficient for current narrow claim scope: `YES — es_ce01_price_v1 LOCKED`;
- OriginalityPack contains real MOTGU material: `YES — opack_ce01_price_v1 APPROVED`;
- positive calibration examples approved: `YES — 4`;
- negative calibration examples approved: `YES — 4`;
- human editorial review form defined: `YES`;
- NeedHypothesis promoted: `NO — remains PROPOSED`.

Therefore:

`GATE D PASS / READY FOR PHASE E ANGLE`

## Next boundary

Proceed to T01.38 Angle using only the approved ContentCase, LocaleVariant, locked EvidenceSet, approved OriginalityPack and calibration examples.

Do not draft yet. Human must approve the Angle or approved Outline checkpoint before Draft, and any new factual claim outside EvidenceSet v1 must route back to evidence review.