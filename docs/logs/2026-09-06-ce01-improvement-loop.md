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

## LOOP-07 — OriginalityPack needs a specific first-party anchor

Observed:

The first OriginalityPack was valid but still operational until a specific real Artwork was selected.

Impact:

Drafting without a concrete first-party anchor could still produce a polished but generic art-price article.

Decision now:

Added hard blocker before Draft and resolved it with runtime-verified Artwork:

`Tranh đường tàu phố cổ Hà Nội — Hoa Lê`

Candidate upgrade:

Journal OriginalityPack should require at least one concrete first-party anchor when the angle depends on a physical work: Artwork, artist quote, studio observation, visitor question or comparable MOTGU-specific material.

Likely phase:

CE04 / CE05.

Status: `RESOLVED IN CE01 / KEEP AS DESIGN RULE`.

---

## LOOP-08 — Current product price/status must be read live, not copied into editorial memory

Observed:

Price and availability can change, while the article may live longer than a product snapshot.

Impact:

Embedding remembered commerce facts risks stale or false statements.

Decision now:

Use a runtime/product component for dynamic facts and keep durable Journal prose evergreen. Draft V2 contains no stale price/stock/status/location snapshot in visible copy.

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

Current Google guidance for generative AI search says core SEO remains the foundation. Google prioritizes useful non-commodity content, clear organization and real first-hand value. Bing likewise ties AI grounding/citations to crawlability, clarity, structure, usefulness, evidence and freshness.

Impact:

Treating SEO, AEO, AIO and GEO as separate copywriting formulas would likely create keyword repetition, thin fan-out pages, artificial FAQ sections and generic machine-oriented prose — the opposite of MOTGU's brand.

Decision now:

Use one shared rule:

`human-first usefulness + first-party value + evidence clarity + machine-legible structure`

Applied now:

- direct answer near the top;
- compact “price can / cannot tell you” map;
- natural question-led headings;
- one real MOTGU Artwork at the centre;
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

Status: `APPLIED TO OUTLINE V2 / CANDIDATE FOR SYSTEM CONTRACT`.

---

## LOOP-12 — Search-feature tactics can age faster than reader value

Observed:

Search presentation features change over time, while clear question-and-answer structure remains useful when it matches real reader jobs.

Impact:

Building content architecture around one rich-result/search feature is brittle.

Decision now:

Use question headings only when they match real reader jobs. Do not add sections or markup solely to chase a search appearance.

Candidate upgrade:

Separate `reader structure` from `search presentation feature` in the publishing contract.

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

## LOOP-15 — Internal implementation language can leak into visible copy

Observed:

Draft V1 passed factual audit but still contained reader-visible phrases such as runtime snapshot, source of truth, hard-code, canonical platform/data and product rules.

Impact:

A factually safe draft can still feel machine-written or like internal documentation rather than a Journal for a visitor.

Decision now:

Draft V2 removes implementation language from visible copy and moves it to internal publishing notes.

Candidate upgrade:

Add a visible-copy boundary check that flags internal implementation vocabulary and requires human-readable wording.

Likely phase:

CE05 / CE06.

Status: `FIXED IN V2 / KEEP AS QUALITY RULE`.

---

## LOOP-16 — Locale-facing media text is not the same as canonical media identity

Observed:

The English Journal V1 inherited Vietnamese alt text from canonical runtime media.

Impact:

The media identity can be correct while the reader-facing accessibility text is wrong for the locale.

Decision now:

Keep the official Vietnamese Artwork title, but produce English alt suggestions for the English Journal.

Candidate upgrade:

Model canonical MediaAsset separately from locale-specific alt/caption/editorial usage.

Likely phase:

CE02 / CE07 / CE08.

Status: `FIXED IN V2 / OPEN FOR DATA MODEL`.

---

## LOOP-17 — Repetition and contract phrasing reveal machine/process residue

Observed:

Draft V1 repeated `facts` heavily and used labels such as Stable/Live facts that were logical for data architecture but less natural for readers.

Impact:

Even when sentences are grammatically correct, repeated system vocabulary can make prose feel generated or over-engineered.

Decision now:

Draft V2 reduces repetition and uses reader-facing labels such as “What stays with the work” and “What you should check today”.

Candidate upgrade:

Language-naturalness evaluation should detect repeated abstract nouns and contract-style labels, not only grammar/readability scores.

Likely phase:

CE06.

Status: `FIXED IN V2 / CANDIDATE EVAL`.

---

## LOOP-18 — Assertion Audit cannot replace human editorial review

Observed:

Draft V1 had zero critical unsupported assertions but Founder still rated natural English 7.5/10 and publish readiness 7/10 because of system-language leakage, repetition and reader-facing phrasing.

Impact:

Factual correctness is necessary but not sufficient for publishability.

Decision now:

Keep factual assertion audit and human editorial review as separate gates.

Candidate upgrade:

Production quality stack should preserve distinct checks for:

- factual support;
- natural language;
- brand voice;
- reader usefulness;
- originality;
- visible/internal boundary.

Likely phase:

CE05 / CE06.

Status: `KEEP AS CORE DESIGN PRINCIPLE`.

---

## T01.43 — Closeout

Founder approved Journal V2 on `2026-09-06`.

This improvement loop is now sufficient evidence for T01.43. No item above automatically changes the global contract; each open item is carried forward as an evidence-backed candidate for the named later phase.

Final closeout summary:

`docs/logs/2026-09-06-ce01-closeout.md`

## T01.44

Decision:

`GO TO CE02`

NeedHypothesis remains `PROPOSED`.

Status: `CE01 IMPROVEMENT LOOP CLOSED FOR PHASE / OPEN ITEMS CARRIED FORWARD`.
