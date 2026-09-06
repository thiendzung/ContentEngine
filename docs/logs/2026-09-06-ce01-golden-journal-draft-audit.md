# TEAM LOG — CE01 GOLDEN JOURNAL DRAFT + ASSERTION AUDIT

Date: 2026-09-06
Project: ContentEngine
Branch: `ce01-golden-journal`

## Context

Founder clarified that the real MOTGU website is still being built and currently has no real published Journal posts.

Important consequence:

`Golden/demo WordPress content != production Content Memory`

The Golden Content Journal used in local development is test/demo content only. It must not cause the engine to believe a production Journal already exists, and it must not force UPDATE/REFRESH or fake Journal-to-Journal internal links.

For the first real Journal candidate:

- decision remains `CREATE`;
- no Journal-to-Journal links;
- internal links go only to useful existing entity surfaces such as Artwork, Artist and Visit;
- future published Journals may link back once they actually exist.

## Artwork fact lock

Runtime artifact:

`artifacts/runtime/ce01-artwork-anchor-20260906T025834Z.json`

SHA-256:

`1f7eda404a8c2c1d7367ccad23afea25c8553308c195b7c881341c6dbb2f771c`

Selected Artwork:

`Tranh đường tàu phố cổ Hà Nội — Hoa Lê`

Stable facts used in Draft:

- year `2025`;
- oil on canvas;
- `60 × 80 cm`;
- approved real Artwork media.

Dynamic facts were verified at runtime but are isolated from durable prose:

- price;
- stock;
- availability;
- location.

Draft/publish design choice:

Use a live Artwork fact card/component for dynamic commerce facts rather than copying them into evergreen Journal prose.

## T01.40 Draft

Created:

`docs/17-CE01-GOLDEN-JOURNAL-DRAFT-EN.md`

Draft properties:

- English LocaleVariant only;
- approved Outline V2 followed;
- direct answer near top;
- price-can / price-cannot map;
- one real MOTGU Artwork at the centre;
- practical Hanoi/take-home section;
- five actionable questions;
- low-pressure CTA;
- no fake FAQ;
- no special AI-only copy;
- no fake existing Journal links;
- dynamic price/status not embedded as durable prose.

## T01.41 Assertion Audit

Created:

`docs/18-CE01-GOLDEN-JOURNAL-ASSERTION-AUDIT.md`

Result:

`PASS FOR HUMAN EDITORIAL REVIEW`

Audit totals:

- critical unsupported assertions: `0`;
- critical contradicted assertions: `0`;
- invented artist intent: `0`;
- investment/appreciation promises: `0`;
- universal fair-price claims: `0`;
- fake scarcity/urgency: `0`;
- dynamic commerce facts presented as durable prose: `0`;
- fake existing Journal links: `0`.

NeedHypothesis remains:

`PROPOSED`

## Improvement-loop candidate

### LOOP-14 — Demo/seed content must not become production Content Memory

Observed:

The canonical local WordPress Golden Content contains test Journal content, while the real MOTGU website has no real published Journal posts yet.

Impact:

If environment/source status is ignored, Content Memory can produce false duplicate detection, wrong CREATE/UPDATE/REFRESH decisions and internal links to content that does not actually exist for users.

Decision now:

For CE01, treat Golden/demo content as `TEST_ONLY`; the first Golden Journal is a new production candidate.

Candidate upgrade:

Content Memory records should preserve at least:

- environment/source kind;
- real publish state;
- canonical public URL when one exists;
- test/demo/fixture flag;
- whether the content is eligible for overlap detection and internal linking.

Likely phase:

CE02 / CE05 / CE08.

Status:

`OPEN / IMPORTANT DATA-BOUNDARY RULE`.

## Next

Human editorial review T01.42.

Review should score:

- useful to target reader;
- feels like MOTGU;
- reader state improved;
- generic/AI-like feel;
- factual issue;
- source-copy concern;
- biggest issue / required edit;
- final verdict.

Do not mark CE01 complete before human review and T01.43/T01.44 closeout.