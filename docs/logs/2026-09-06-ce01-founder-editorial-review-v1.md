# TEAM LOG — CE01 FOUNDER EDITORIAL REVIEW — JOURNAL V1

Date: 2026-09-06
Project: ContentEngine
Branch: `ce01-golden-journal`
Phase: `CE01 / PR-E — Walking Skeleton`
Task: `T01.42 — Human editorial review`

Reviewed candidate:

`docs/17-CE01-GOLDEN-JOURNAL-DRAFT-EN.md` — Draft EN V1

## Founder review outcome

Direction: `CONCEPT APPROVED / EDITORIAL REVISION REQUIRED`

This is not a strategy rework. Angle A and Outline V2 remain valid.

Review scores supplied by Founder:

- idea / positioning: `9/10`;
- structure: `8.5/10`;
- trust / caution: `9.5/10`;
- natural English: `7.5/10`;
- on-page search quality: `8.5/10`;
- MOTGU brand tone: `9/10`;
- publish readiness: `7/10`.

Founder conclusion:

- concept does not need to be rebuilt;
- outline does not need to be rebuilt;
- one editorial revision should focus on humanizing English, removing system language from visible content, reducing repetition, and fixing English alt text;
- after that revision the candidate is expected to be strong enough to serve as the first real MOTGU Journal, subject to final Founder confirmation.

## Required changes

### R1 — Remove internal system language from visible copy

Remove reader-visible wording such as:

- source of truth;
- canonical WordPress/WooCommerce data;
- runtime snapshot;
- hard-code;
- durable published prose;
- product rules.

Public copy should simply say that current price, availability and viewing details can change and should be checked on the Artwork page.

### R2 — Locale-correct image alt text

For the English Journal, use English descriptive alt text while keeping the official Vietnamese Artwork title unchanged.

Examples:

- `Oil-on-canvas painting Tranh đường tàu phố cổ Hà Nội by Hoa Lê`;
- `Detail of the paint surface of Tranh đường tàu phố cổ Hà Nội`.

Do not invent an English Artwork title.

### R3 — Humanize English

Apply Founder-polished wording where useful, including:

- `Specialists may consider several concrete facts about a work, but the final decision is still personal.`
- `One term that often sounds more technical than it needs to is provenance.`
- `Your first purchase does not need to prove that you understand art. You only need to understand the work well enough to choose it without feeling pushed.`

### R4 — Reduce repetition of `facts`

Keep `facts` as a core editorial idea, but reduce repetition by using natural alternatives where accurate:

- details;
- documented information;
- what is known about the work;
- current information;
- verified information.

### R5 — Make static/dynamic distinction human-facing

Replace system-like labels:

- `Stable facts about the work`;
- `Live facts that can change`;

with reader-facing labels such as:

- `What stays with the work`;
- `What you should check today`.

### R6 — Rewrite shipping in visitor language

Avoid exposing product-contract wording.

Preferred direction:

`Depending on the work and destination, bringing a painting home may also involve packaging, shipping and insurance.`

Keep oversize quote wording bounded.

### R7 — Give the five questions distinct jobs

Use:

1. What exactly is this work?
2. What helps explain its context?
3. What documentation comes with it?
4. What will bringing it home involve?
5. Do I actually want to live with it?

### R8 — Remove CTA repetition

Keep the heading:

`If one work keeps pulling you back, ask about it`

Do not repeat the same sentence immediately in body copy.

### R9 — Keep first-Journal linking rule

Production currently has no real published Journal posts.

Keep links only to useful existing entity surfaces:

- Artwork;
- Artist;
- Visit.

Do not invent Journal-to-Journal links.

## Improvement-loop candidates from this review

### LOOP-CANDIDATE-A — Implementation language leakage

Rule candidate:

`internal implementation language must never leak into visible copy`

Suggested future evaluator:

- flag implementation/database/platform vocabulary in visible article output unless reader-relevant;
- distinguish public copy from implementation notes as separate artifact fields.

Likely phase: CE05 / CE06 / CE08.

### LOOP-CANDIDATE-B — Locale-aware media text

Canonical media alt text can be Vietnamese while an English LocaleVariant needs an English alt suggestion.

Rule candidate:

Media identity is shared, but locale-facing alt/caption copy should be generated/reviewed per LocaleVariant without translating an official Artwork title unless an approved localized title exists.

Likely phase: CE05 / CE07 / CE08.

### LOOP-CANDIDATE-C — System-contract phrasing is not public prose

A statement may be factually correct and still fail editorial quality when it sounds like a product/data contract.

Rule candidate:

Quality review needs a `reader_language_vs_system_language` check in addition to factual correctness.

Likely phase: CE06.

### LOOP-CANDIDATE-D — Repetition can reveal machine/process residue

Repeated abstract nouns such as `facts` made a correct draft feel more artificial.

Rule candidate:

Language-naturalness review should check local repetition and semantic variety without forcing synonym replacement where precision matters.

Likely phase: CE06.

## Next

1. Revise Draft EN V1 → V2 using only the approved changes above.
2. Re-run Assertion Audit because wording changed.
3. Keep T01.44 open.
4. Ask Founder for final confirmation on V2 before CE01 GO/FIX/STOP closeout.
