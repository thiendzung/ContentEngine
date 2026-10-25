# Content Production v1 RC1 — Manual WordPress Publish

**Issue:** #417  
**Base:** `b1a94059917d9848ebc061b8f85826c0d343bd61`  
**Release type:** bounded content-production release candidate  
**Publication mode:** Founder manual WordPress Draft/publish  
**Status:** RC1 — requires exact-SHA local verification before production use

## 1. Goal

Use the existing ContentEngine production pipeline to produce a small batch of evidence-grounded bilingual MOTGU content optimized for useful search discovery and AI/search retrieval, then stop at a deterministic approved package.

This release does **not** build a CMS, auto-publisher, new workflow engine or new SEO scoring system.

Canonical flow:

```text
customer/search question
→ evidence/originality
→ Angle
→ Outline
→ independent EN + vi-VN Writer
→ Human Voice + quality gates
→ Founder final approval
→ deterministic review package
→ Founder manually creates/reviews WordPress Draft
→ Founder publishes
```

ContentEngine publication side effects remain zero.

## 2. Why this release is possible now

Current main already contains the reusable Journal production path and three human gates. Existing repository state proves:

- browser/manual intake exists;
- Start → Angle exists;
- Angle approval → Outline exists;
- independent EN / vi-VN Writer lanes exist;
- Review/Revise, Assertion Audit, Source-copy and Deep Quality exist;
- final approval can create approved ContentVersions without publishing;
- deterministic package/export capability exists;
- PR #416 added a deterministic provenance-bound manual package producer.

What is **not** yet proven for this RC is one exact-SHA local run of the new five-item MAP-v3 batch. Therefore this document authorizes no claim of `PASS_LOCAL_CONTENT_PRODUCTION_READY` by itself.

## 3. Locked QA/QC source pack

Reviewed 2026-10-25:

| Artifact | SHA-256 |
| --- | --- |
| `MOTGU_ContentEngine_QAQC_Prepublish_Pack_2026_v1.zip` | `90251cc14edda5f57398137a23a08334a8bf445b055df71b76cf800d40868eaa` |
| `MOTGU_Master_Keyword_Content_Map_2026_v3_QA_QC.xlsx` | `e22a86548784bed9438f992053dae8c114dd41d544e8f30cec6f2b0b691e7782` |
| `MOTGU_ContentEngine_QAQC_Gates_2026_v1.0_PROPOSED.md` | `c7267117591aabe72baa12ca420aabe8b50027b26697deb8af86f2b89d977dd4` |
| `MOTGU_ContentEngine_14_Point_PrePublish_Check_v1.0.md` | `2583a4b8684bd3a67ab93c5553656ac14e6bd9cf9221955c8847d94ab9b7a8d6` |

The QA/QC pack is a release input, not a replacement for Tier-0 repository contracts. If a live operational/business fact conflicts with the pack, fail closed and use the current approved owner.

## 4. RC1 production batch

Freeze the first batch to current MAP-v3 intent owners:

| Order | ID | Type | Primary English intent | Proposed owner URL |
| ---: | --- | --- | --- | --- |
| 1 | G01 | Pillar | where to buy original art in Hanoi | `/guides/buy-original-art-hanoi/` |
| 2 | G02 | Pillar | how to bring a painting home from Vietnam | `/guides/take-painting-home-from-vietnam/` |
| 3 | Q05 | Cluster | original painting vs hand painted reproduction | `/guides/original-vs-hand-painted-copy/` |
| 4 | Q07 | Cluster | what does a certificate of authenticity prove | `/guides/what-does-art-certificate-prove/` |
| 5 | Q06 | Cluster | artwork condition report before buying online | `/guides/artwork-condition-report-online/` |

### Removed from the old five-case campaign

The previous standalone C05 “7 Questions to Ask Before Buying Original Art” is **not** an independent RC1 page. MAP v3 folds this job into G01 and related owner pages. Creating another indexable C05 URL would increase intent overlap/cannibalization without a distinct owner.

The previous C02 mapping is represented by current Q05. The RC1 identifier follows the current MAP, not the historical pilot name.

## 5. Search / AI optimization contract

This release optimizes for SEO + AI/search visibility through content quality and retrievability, not tricks.

Required:

- one primary intent owner URL per locale;
- answer the user question directly near the start when appropriate;
- useful headings that reflect real subquestions;
- exact evidence provenance and current dates for time-sensitive claims;
- original MOTGU evidence when a claim depends on an actual Artist/Artwork/Piece;
- concise tables/checklists/decision paths only when they improve the answer;
- internal links to the correct Pillar/Cluster/Artist/Artwork/Visit owner;
- title/H1/meta proposal aligned to intent, without keyword stuffing;
- crawlable public text and truthful schema proposal;
- explicit uncertainty and `must_not_claim`;
- EN and vi-VN are independent editorial lanes, not blind translation.

Do **not** gate on:

- word count;
- keyword density;
- Rank Math score;
- fixed 50–80 word chunks;
- `llms.txt`;
- invented AI-specific schema;
- FAQ rich-result expectations;
- “AEO/GEO score”.

## 6. Package contract

For each RC1 item, the final review package must include at minimum:

- stable content ID;
- content type;
- locale;
- customer job / primary intent;
- proposed intent-owner URL;
- final title/H1/meta proposal;
- answer summary;
- primary keyword + bounded supporting terms;
- exact final visible content bytes;
- content/version hash;
- EvidenceSet / source refs;
- Originality/quality refs;
- cited-as-of date;
- author/reviewer refs;
- rights refs where applicable;
- `must_not_claim`;
- Artist/Artwork/Piece stable refs when used;
- internal-link plan;
- schema proposal;
- QA result;
- Founder final approval bound to exact bytes.

Missing required evidence is `NEED_EVIDENCE / STOP`, not permission to infer.

## 7. QA/QC admission

Before Founder publishes a WordPress page:

1. apply the QA/QC gate set for that content type;
2. all applicable CHẶN items must PASS with evidence;
3. expert/legal/conservation review is mandatory where the risk class requires it;
4. inspect the final WordPress Draft on mobile;
5. verify owner URL, canonical/hreflang and schema proposal;
6. verify no live price, stock, address, hours, policy, carrier, legal or artist claim was invented;
7. Founder reviews the exact final hash;
8. Founder publishes manually.

Passing ContentEngine quality is not itself WordPress Production GO.

## 8. Exact local verification required

Agent Local must verify the candidate SHA without polling loops.

Minimum RC1 proof:

- clean exact checkout;
- release manifest and active docs agree;
- operational preflight is READY in the authorized environment;
- no unexpected migration is required;
- one-shot worker path is available;
- one bounded RC1 item can be created from the locked brief and reach the first human gate without case-specific code;
- no publication side effect;
- no direct WordPress, Astro, Git publication or MOTGU production mutation;
- targeted/full checks required by the changed scope pass;
- returned evidence includes exact SHA and blocker/state.

If the runtime blocks on evidence, provider, configuration or a true defect, report the first exact blocker. Do not weaken gates to make the release look green.

## 9. Release exit

RC1 becomes usable for batch content production only after:

`PASS_CONTENT_PRODUCTION_V1_RC1`

That status requires reviewed exact-SHA Agent Local evidence. It does **not** mean any article has been published.

Founder alone authorizes merge and manual publication.
