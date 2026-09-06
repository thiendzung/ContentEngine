# TEAM LOG — CE01 IMPROVEMENT LOOP

Date: 2026-09-06
Project: ContentEngine
Branch: `ce01-golden-journal`

Purpose:

Keep a running list of real problems, weak points and useful upgrades observed while CE01 is executed. This log feeds T01.43/T01.44 and later roadmap work.

Rule:

- record observations now;
- do not silently change global contracts from one test;
- separate `FIX NOW` from `CANDIDATE UPGRADE`;
- only promote an upgrade when evidence justifies it.

---

## LOOP-01 — Search evidence is not customer truth

Observed:

The real-seed run produced useful price/search signals, but no MOTGU-direct visitor signal, contradiction signal, site-behaviour signal or direct MARKET observation.

Impact:

Search can justify testing `price`, but cannot prove the NeedHypothesis.

Decision now:

Keep NeedHypothesis `PROPOSED`.

Candidate upgrade:

Collect reviewed MOTGU-direct questions, inquiries and post-publish behaviour as separate signal lanes.

Likely phase:

CE08–CE10.

Status: `OPEN / EXPECTED LIMITATION`.

---

## LOOP-02 — Deeper search providers did not clearly improve final selected URLs

Observed:

Fresh PR-B run called Tavily and Exa, but the selected URLs still came from the same Google-origin set.

Impact:

Extra provider cost may not always improve source selection.

Decision now:

Do not expand PR-E scope. Evidence Research later used manually selected stronger sources instead.

Candidate upgrade:

Measure provider contribution: unique useful source found, source promoted, evidence accepted, cost and latency.

Likely phase:

CE04 / CE10.

Status: `OPEN`.

---

## LOOP-03 — Opportunity pillar could be synthesized from unrelated clusters

Observed:

Earlier PR-C logic produced a broad choosing-confidence Pillar from `price + negotiation` even though no usable choosing cluster existed.

Impact:

Founder hypothesis could leak back into output and look search-supported when it was not.

Decision now:

Fixed with Pillar coherence guard + regression test.

Candidate upgrade:

Keep explicit promise-to-core-cluster coherence checks in production Opportunity Map.

Likely phase:

CE04 / CE05.

Status: `FIXED IN CE01`.

---

## LOOP-04 — IDs must come from artifacts, never be reconstructed by hand

Observed:

A manually inferred Opportunity ID was wrong and selected rerun correctly failed with `opportunity_not_found`.

Impact:

Manual ID reconstruction can create false selection or broken handoff.

Decision now:

Always read canonical IDs from generated artifacts.

Candidate upgrade:

Human-selection UI should select by displayed opportunity object and persist its artifact/version ref; humans should never type IDs.

Likely phase:

CE02 / CE05.

Status: `PROCESS FIX APPLIED`.

---

## LOOP-05 — Internal workflow terms are too technical for founder review

Observed:

Terms such as `Angle`, `OriginalityPack`, `EvidenceSet`, `LocaleVariant` required a plain-language explanation before the workflow felt obvious.

Impact:

Good internal contracts can still create unnecessary review friction.

Decision now:

Explain each human gate in plain language and keep technical IDs secondary.

Candidate upgrade:

UI labels should lead with the human question, for example:

- Angle → “Bài này sẽ đi theo góc nào?”
- Outline → “Bài sẽ gồm những phần nào?”
- EvidenceSet → “Thông tin nào đã được kiểm chứng?”
- OriginalityPack → “MOTGU có gì riêng để nói?”

Likely phase:

CE05 / CE06 UI.

Status: `OPEN`.

---

## LOOP-06 — Evidence locators are weaker than the intended production contract

Observed:

CE01 EvidenceSet has clear source URLs and bounded claim mappings, but external sources do not yet have strong paragraph/section locators stored as first-class records.

Impact:

Manual assertion review is possible, but production audit/replay would be slower and less exact.

Decision now:

Accept for manual CE01, keep claim scope narrow, and do not invent unsupported detail.

Candidate upgrade:

Evidence record should preserve source document version/fingerprint + exact locator/quote span or normalized chunk ID.

Likely phase:

CE02 / CE04.

Status: `OPEN`.

---

## LOOP-07 — OriginalityPack is valid but still too operational without a specific Artwork

Observed:

The current pack contains real MOTGU product/commerce rules and brand posture, but no specific verified Artwork has yet been selected for the Golden Journal.

Impact:

Drafting now could still produce a polished but generic art-price article.

Decision now:

Add hard blocker before T01.40:

`ARTWORK_ANCHOR_REQUIRED_BEFORE_DRAFT`

Candidate upgrade:

Journal OriginalityPack should require at least one concrete first-party anchor when the angle depends on a physical work: Artwork, artist quote, studio observation, visitor question or comparable MOTGU-specific material.

Likely phase:

CE04 / CE05.

Status: `RESOLVED IN CE01 BY RUNTIME-VERIFIED ARTWORK ANCHOR`.

---

## LOOP-08 — Current product price/status must be read live, not copied into editorial memory

Observed:

Price and availability can change, while the article may live longer than a product snapshot.

Impact:

Embedding remembered commerce facts risks stale or false statements.

Decision now:

Use a runtime/product component for dynamic facts and keep durable Journal prose evergreen. Draft V1 isolates the runtime snapshot as an internal editorial block rather than durable public prose.

Candidate upgrade:

Use runtime product references/components or publish-time verification for dynamic facts rather than copying them into durable prose when unnecessary.

Likely phase:

CE07 / CE08.

Status: `PROCESS DESIGN APPLIED / PRODUCTION IMPLEMENTATION LATER`.

---

## LOOP-09 — Manual approvals create repeated docs-sync work

Observed:

CE01 intentionally records human gates in Markdown/PR state. This is clear but requires repeated manual synchronization between chat decision, task list, runbook and artifact docs.

Impact:

Fine for one walking skeleton; inefficient at scale and easy to drift.

Decision now:

Keep manual workflow for CE01 to test the content contract first.

Candidate upgrade:

Persist Approval records with subject artifact/version, reviewer, decision, timestamp and reason; derive UI/status from those records instead of copying state into many files.

Likely phase:

CE02 / CE03 / CE05.

Status: `OPEN`.

---

## LOOP-10 — Human-gated workflow should avoid premature writing

Observed:

The most useful control so far is stopping between Opportunity → Content Input → Angle → Outline instead of generating a long draft immediately.

Impact:

This reduces wasted writing and makes unsupported scope expansion visible early.

Decision now:

Keep explicit human gates for CE01.

Candidate upgrade:

Production workflow may automate low-risk steps but must preserve approval checkpoints when angle, factual scope or originality changes materially.

Likely phase:

CE03 / CE05.

Status: `KEEP AS DESIGN PRINCIPLE`.

---

## LOOP-11 — SEO / AEO / AIO / GEO should not become four separate writing systems

Observed:

Current Google guidance for generative AI search says core SEO remains the foundation. Google explicitly prioritizes useful non-commodity content, clear organization and real first-hand value, while saying there is no special AI schema, no requirement to split content into tiny chunks, and no need to rewrite pages for AI systems. Bing likewise ties AI grounding/citations to crawlability, clarity, structure, usefulness, evidence and freshness.

Impact:

Treating SEO, AEO, AIO and GEO as separate copywriting formulas would likely create keyword repetition, thin fan-out pages, artificial FAQ sections and generic machine-oriented prose — the opposite of MOTGU's brand and the opposite of current official guidance.

Decision now:

Revise Golden Journal Outline V2 around one shared rule:

`human-first usefulness + first-party value + evidence clarity + machine-legible structure`

Applied now:

- direct answer near the top;
- compact “price can / cannot tell you” map;
- natural question-led headings;
- one real MOTGU Artwork moved to the centre;
- practical Hanoi/take-home context emphasized over generic valuation theory;
- real Artwork image requirement added;
- adjacent fan-out questions covered inside one coherent page;
- no forced FAQ schema or keyword variants;
- no AI-only markup or artificial chunking;
- trust/source layer and entity clarity added.

Candidate upgrade:

Turn these principles into a reusable Journal outline/eval contract:

1. `primary_answer_present`;
2. `first_party_anchor_present`;
3. `non_commodity_value_present`;
4. `adjacent_intents_covered_without_thin_pages`;
5. `critical_claims_traceable`;
6. `entity_identity_clear`;
7. `multimodal_support_relevant`;
8. `dynamic_facts_verified`;
9. `no_search_only_section`;
10. `natural_next_action_present`.

Likely phase:

CE05 / CE06 / CE08.

References reviewed 2026-09-06:

- Google Search Central: Optimizing your website for generative AI features on Google Search;
- Google Search Central: AI features and your website;
- Bing Webmaster Guidelines / AI Performance guidance.

Status: `APPLIED TO OUTLINE V2 / CANDIDATE FOR SYSTEM CONTRACT`.

---

## LOOP-12 — FAQ/search-feature tactics can age faster than reader value

Observed:

Google deprecated the FAQ rich result in May 2026. At the same time, clear question-and-answer structure is still useful to readers and Bing explicitly recommends clear sections and FAQ-style content where appropriate for AI citation clarity.

Impact:

Building a content architecture around a specific rich-result feature is brittle. Removing useful question structure just because a search feature changed would also be wrong.

Decision now:

Use question headings only when they match real reader jobs. Do not add an FAQ section or FAQ structured data solely to chase search appearance.

Candidate upgrade:

Separate `reader structure` from `search presentation feature` in the publishing contract. Search features can change without forcing editorial rewrites.

Likely phase:

CE05 / CE08.

Status: `OPEN / DESIGN PRINCIPLE`.

---

## LOOP-13 — Runtime verification closes the seed/data boundary

Lesson:

`Static seed data identifies the entity, but dynamic commerce facts require runtime verification.`

Applied to CE01: the Golden importer seed identified the Artwork, while the current WordPress/WooCommerce runtime locked the facts used for T01.40. Price, stock, sale status and physical location remain dynamic.

Status: `APPLIED`.

---

## LOOP-14 — Demo/seed content must not become production Content Memory

Observed:

The canonical local WordPress Golden Content contains test Journal content, while Founder confirmed the real MOTGU website is still being built and currently has no real published Journal posts.

Impact:

If environment/source status is ignored, Content Memory can produce false duplicate detection, wrong CREATE/UPDATE/REFRESH decisions and internal links to content that does not actually exist for users.

Decision now:

For CE01, treat Golden/demo content as `TEST_ONLY`. The Golden Journal under PR-E is the first real production candidate. Do not add Journal-to-Journal links yet.

Candidate upgrade:

Content Memory records should preserve:

- environment/source kind;
- actual publish state;
- canonical public URL when one exists;
- test/demo/fixture flag;
- eligibility for overlap detection;
- eligibility for internal linking.

Likely phase:

CE02 / CE05 / CE08.

Status: `OPEN / IMPORTANT DATA-BOUNDARY RULE`.

---

## LOOP-15 — Implementation language can leak into reader-visible copy

Observed:

Founder review of Draft EN V1 found technically correct phrases such as `source of truth`, `canonical WordPress/WooCommerce data`, `runtime snapshot`, `hard-code`, `durable published prose` and `product rules` inside or too close to visible reader copy.

Impact:

A factually correct Draft can still feel like system documentation instead of a human Journal. This reduced publish readiness even though the assertion audit had already passed.

Decision now:

Draft EN V2 moves implementation language into a separate internal publishing-notes section and leaves only reader-relevant wording in the visible article.

Candidate upgrade:

Add a `reader_language_vs_system_language` quality check. Visible copy and implementation notes should be separate artifact fields, not one mixed body.

Likely phase:

CE05 / CE06 / CE08.

Status: `FIXED IN V2 / CANDIDATE SYSTEM RULE`.

---

## LOOP-16 — Locale-facing image text must be independent from canonical media identity

Observed:

The canonical Artwork media had Vietnamese alt text, while the first Journal LocaleVariant is English. Draft V1 reused the canonical Vietnamese alt text in the English article plan.

Impact:

Shared media identity does not mean all reader-facing media text should be identical across locales. Reusing canonical alt text can create mixed-language output.

Decision now:

Draft EN V2 keeps the official Vietnamese Artwork title unchanged but provides English descriptive alt suggestions.

Candidate upgrade:

MediaAsset identity should be shared, while alt/caption suggestions are locale-facing fields. Do not translate official Artwork titles unless an approved localized title exists.

Likely phase:

CE05 / CE07 / CE08.

Status: `FIXED IN V2 / CANDIDATE DATA CONTRACT`.

---

## LOOP-17 — Repetition and contract phrasing can reveal machine/process residue

Observed:

Founder review found excessive repetition of the abstract noun `facts` and system-like labels such as `Stable facts` / `Live facts` and product-contract phrasing around shipping.

Impact:

The article was correct but less natural. Repetition made the writing feel more generated/editorial-process-driven than reader-driven.

Decision now:

Draft EN V2 keeps `facts` where precision matters but uses natural alternatives such as details, documented information, what is known, and current information. Public labels become `What stays with the work` and `What you should check today`. Shipping language is rewritten around the visitor’s real task.

Candidate upgrade:

Language-naturalness evaluation should detect local repetition and contract/system phrasing without forcing synonym replacement where precision matters.

Likely phase:

CE06.

Status: `FIXED IN V2 / CANDIDATE EVALUATOR`.

---

## LOOP-18 — Human review catches quality failures that assertion audit cannot

Observed:

Assertion Audit V1 correctly returned zero critical unsupported claims, but Founder still rated natural English lower and publish readiness at 7/10 because of reader-language issues.

Impact:

Factual correctness is necessary but not sufficient. An automated evidence audit cannot certify naturalness, brand feel or publish readiness.

Decision now:

Keep Assertion Audit and Human Editorial Review as distinct gates.

Candidate upgrade:

Never let an evidence/claim evaluator self-certify final editorial quality. Production quality must preserve separate deterministic/evidence checks, AI-assisted quality checks and human approval.

Likely phase:

CE05 / CE06.

Status: `KEEP AS DESIGN PRINCIPLE`.

---

## Current PR-E checkpoint

- Angle A selected;
- Outline V2 Founder approved;
- runtime Artwork fact lock PASS;
- Draft EN V1 created and reviewed by Founder;
- Founder V1 review: `CONCEPT APPROVED / EDITORIAL REVISION REQUIRED`;
- Draft EN V2 created with required editorial fixes;
- Assertion Audit V2: `PASS / ZERO CRITICAL UNSUPPORTED ASSERTIONS`;
- final Founder confirmation on V2: `NEXT`;
- NeedHypothesis remains `PROPOSED`.

Founder review evidence:

`docs/logs/2026-09-06-ce01-founder-editorial-review-v1.md`

This log is living evidence for T01.43. Do not mark CE01 Gate T01.44 complete until Founder confirms the revised Journal and the final GO/FIX/STOP decision is recorded.
