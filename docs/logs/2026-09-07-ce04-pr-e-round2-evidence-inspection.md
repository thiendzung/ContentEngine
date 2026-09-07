# CE04 PR-E — Round 2 Evidence Inspection

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
PR: #28
Status: `PIPELINE PASS / EVIDENCE QUALITY FAIL / BLOCKED`

## Scope

This inspection reads the already-persisted Round 2 EvidenceSet and its DB rows. No provider was called, no Evidence Research was run, no Evidence relation was changed, and no EvidenceSet was locked.

Artifact:

`/Users/thiendung/MOTGU-AI/ContentEngine/artifacts/research/ce04-evidence-research-v1-20260907T143203Z.json`

Artifact SHA-256:

`8c6325822a22c01c76d5f07268b0722540f949e077dbff582b3eddf66ce13a81`

Round 2 EvidenceSet:

`e9c7f1b9-c812-4ca5-ba36-fdd8af99b8ec / v2 / draft / unlocked`

Round 1 EvidenceSet remains unchanged:

`2e423158-42af-4188-9954-90784b8cf37a / v1 / draft / unlocked`

## Locked DB state confirmed

- ContentCase: exactly one, `9ec6133b-5f14-46d0-9866-e3b049e537b5`, type `journal`.
- ContentOpportunity: `068991ab-de34-4787-9c38-8935c3f0e2da`.
- NeedHypothesis: `530bdd27-f008-4910-9b3b-df83e007cfa2`, `PROPOSED`.
- ContentExperiment: `0551da17-046a-4104-a506-9772680a6133`, `PLANNED / PENDING`.
- ContentRun total: `2`.
- KnowledgeCandidate total: `0`.
- Round 2: 3 SourceDocuments, 8 Claims, 8 Evidence.
- Round 2 relation counts: `context_only=8`, `supports=0`, `contradicts=0`, `qualifies=0`.

## Full Evidence review

All eight rows have a non-empty locator and excerpt, and every excerpt matches its persisted readable SourceDocument after canonical normalization. All eight rows are from the same SourceDocument and are therefore not independent observations.

### Evidence 1

```text
evidence_id: d7d20443-5561-4722-9d4f-1b38a8777b7d
claim_id: 3fa9e7e5-226d-4657-80e1-d7e7c33864cf
claim: [Skip to content](https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB#main)
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:1
excerpt: [Skip to content](https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB#main)
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — page navigation text is not a valuation criterion
reviewer_note: WEAK/OFF_SCOPE
why_context_only: page chrome; claim is unverified and provides no substantive source proposition
```

### Evidence 2

```text
evidence_id: 22944832-b892-4693-98ac-813bb14f732e
claim_id: ba83df47-9456-4272-965d-f4588080c43f
claim: ![Image 1: How to Value Art: A Collector’s Guide to Artwork Valuation and the Factors That Determine a Painting's Worth](https://maddoxgallery.com/cdn/shop/articles/how-to-value-art-a-guide-to-artwork-valuation_blog_header_a6871443-4c1b-4494-9b28-92ef123a55ed.jpg?v=1787044685&width=320)
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:3
excerpt: ![Image 1: How to Value Art: A Collector’s Guide to Artwork Valuation and the Factors That Determine a Painting's Worth](https://maddoxgallery.com/cdn/shop/articles/how-to-value-art-a-guide-to-artwork-valuation_blog_header_a6871443-4c1b-4494-9b28-92ef123a55ed.jpg?v=1787044685&width=320)
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — image alt text names the topic but gives no factor or test
reviewer_note: WEAK/OFF_SCOPE
why_context_only: image markdown/alt text; claim is not an atomic valuation proposition
```

### Evidence 3

```text
evidence_id: 44755104-4f05-45c0-a18d-45e42938db42
claim_id: cae5b9a6-16f7-437a-bf82-eaffa466ce7f
claim: How to Value Art: A Collector’s Guide to Artwork Valuation and the Factors That Determine a Painting's Worth
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:5
excerpt: How to Value Art: A Collector’s Guide to Artwork Valuation and the Factors That Determine a Painting's Worth
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — title-only text does not explain how to judge a price
reviewer_note: WEAK/OFF_SCOPE
why_context_only: article title; no checkable factor, method, or source-backed conclusion
```

### Evidence 4

```text
evidence_id: 7e76a869-8354-44b2-bbf2-906803f72f52
claim_id: 784622c4-ca3f-4485-bbc9-7ae62ba0fcb8
claim: **Whether you have inherited a painting, are considering a sale or are building a collection with an eye on long-term value, knowing how to value art is essential.
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:7
excerpt: **Whether you have inherited a painting, are considering a sale or are building a collection with an eye on long-term value, knowing how to value art is essential.
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — frames audience situations but gives no price-evaluation criterion
reviewer_note: USEFUL_CONTEXT
why_context_only: broad introductory/editorial framing; not an atomic claim about a valuation factor
```

### Evidence 5

```text
evidence_id: ae69fd12-b69f-403f-b73c-4acdf5ff9647
claim_id: c2e26431-90ce-431d-ab8f-5ab781deeeb5
claim: Yet artwork valuation remains one of the most opaque corners of the art world, full of jargon, subjectivity and variables that are rarely explained clearly.
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:8
excerpt: Yet artwork valuation remains one of the most opaque corners of the art world, full of jargon, subjectivity and variables that are rarely explained clearly.
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — describes difficulty but does not identify a reliable way to judge fairness
reviewer_note: USEFUL_CONTEXT
why_context_only: general framing about opacity/subjectivity; no specific factor is stated or verified
```

### Evidence 6

```text
evidence_id: dc4ff586-2726-41cb-be5d-3b33e875c0c8
claim_id: 7ceeb9a2-22a1-4330-bb8b-a290f7aab6e2
claim: Here is what actually determines the value of a painting, from key influencing factors to the process of assessing an artwork’s true worth, so you know what to expect when you seek a professional valuation.**
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:10
excerpt: Here is what actually determines the value of a painting, from key influencing factors to the process of assessing an artwork’s true worth, so you know what to expect when you seek a professional valuation.**
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — promises factors but does not state any factor in the persisted excerpt
reviewer_note: USEFUL_CONTEXT
why_context_only: transition/marketing sentence; no actual factor or decision rule is present
```

### Evidence 7

```text
evidence_id: 96c4906c-074b-40a0-8d00-09da9b024446
claim_id: 499cd653-8438-4982-b304-1dd2e502a9db
claim: [![Image 2: A framed art print hangs behind a couch on an art advisory office wall, as clients ask, “How do I find out what a painting is worth?”](https://cdn.shopify.com/s/files/1/1032/8771/8225/files/Screenshot_2026-07-15_at_16.04.46.png?v=1784127902&width=960)](https://maddoxgallery.com/products/david-hockney-water-made-of-lines-t210-1978)
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:11
excerpt: [![Image 2: A framed art print hangs behind a couch on an art advisory office wall, as clients ask, “How do I find out what a painting is worth?”](https://cdn.shopify.com/s/files/1/1032/8771/8225/files/Screenshot_2026-07-15_at_16.04.46.png?v=1784127902&width=960)](https://maddoxgallery.com/products/david-hockney-water-made-of-lines-t210-1978)
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — embedded marketing image asks a related question but supplies no answer
reviewer_note: USEFUL_CONTEXT
why_context_only: image/marketing link; related question is not factual pricing guidance
```

### Evidence 8

```text
evidence_id: ce46c569-2e31-4914-a135-2e702a148381
claim_id: 5678c807-1715-44a7-9ff6-93b07eadc222
claim: Every artwork has a value, but arriving at that figure is rarely straightforward.
relation: context_only
source_url: https://maddoxgallery.com/blogs/news/how-to-value-art-a-guide-to-artwork-valuation?srsltid=AfmBOor8-LhPD_hIDdxHZzke_fzuR3G4i2EDFpF5sNsM4kib6FN4kkgB
source_domain: maddoxgallery.com
source_type: editorial_or_unknown
commercial_bias: unknown
authority_hint: null
provider: jina
discovered_by: serper
found_via: google_organic
locator: document_sentence:13
excerpt: Every artwork has a value, but arriving at that figure is rarely straightforward.
source_document_id: f9d6f735-2451-528e-9649-a0453c3f0a10
independent_from_other_rows: no — same source document/domain as all other Round 2 Evidence
directly_helps_answer_O4: no — general observation, not a buyer-facing evaluation test
reviewer_note: USEFUL_CONTEXT
why_context_only: broad introductory statement with no actionable or independently verifiable pricing factor
```

## Source-level summary

### Evidence-bearing sources

| SourceDocument | Domain | Evidence count | Source type | Commercial bias | Authority hint |
|---|---|---:|---|---|---|
| `f9d6f735-2451-528e-9649-a0453c3f0a10` | `maddoxgallery.com` | 8 | `editorial_or_unknown` | `unknown` | `null` |
| `dea1c006-699d-5dc0-bbc0-7ae583df5237` | `paintingrecognition.com` | 0 | `editorial_or_unknown` | `unknown` | `null` |
| `07c996e8-00ca-5135-bb9c-da840d8bfbf1` | `wcc.art` | 0 | `editorial_or_unknown` | `unknown` | `null` |

The run persisted three readable SourceDocuments, but the eight Evidence rows represent only one unique URL/domain: `maddoxgallery.com` / `8 rows`. `paintingrecognition.com` and `wcc.art` contributed no Evidence rows. Therefore independent-source coverage is `1`, not `3`.

All eight Evidence rows share:

- provider/reader: `jina`;
- discovered_by: `serper`;
- found_via: `google_organic`;
- source type distribution: `editorial_or_unknown=8`;
- commercial bias distribution: `unknown=8`;
- authority hint distribution: `null=8`;
- `search_rank_used_as_authority=false`.

The `context_only` classification is explained by the conservative rule for unknown/unclassified sources plus the actual excerpt content. The excerpts are page chrome, image/title metadata, generic introduction, or marketing framing. None is an atomic, checkable pricing factor; none directly answers how a first-time buyer can judge whether an original artwork price makes sense.

No source appears strong enough, from the persisted metadata and excerpts, to justify changing a row to factual `supports` in this inspection. Maddox Gallery and WCC have commercial/investment context; Painting Recognition is a free valuation guide with no authority metadata. The classifier is too coarse because it collapses all three to `editorial_or_unknown` and does not expose commercial/authority distinctions, but its refusal to promote these specific excerpts is not too conservative.

## Diagnosis

The failure is a combination, with two primary causes:

1. **SOURCE_SELECTION — primary.** All eight rows came from one Maddox Gallery URL. The other two readable URLs produced zero Evidence. The run therefore cannot meet the independent-source minimum, and the selected source is not a neutral or primary authority for default buyer guidance.
2. **CLAIM_EXTRACTION — primary.** The extractor persisted three page-structure rows (navigation, image metadata, title) and five broad introductory/marketing sentences. It did not select the substantive valuation-factor passages implied by the query. All eight claims remain `unverified` and none directly answers O4.
3. **SOURCE_CLASSIFICATION — contributing.** The source metadata is under-classified: all sources are `editorial_or_unknown`, `commercial_bias=unknown`, and `authority_hint=null`. This loses useful commercial-risk and authority distinctions. However, given the actual excerpts, `context_only` is the safe result and reclassifying them alone would not create valid support.
4. **QUERY/ROUTING — contributing, not the sole cause.** The query is semantically aligned with valuation factors. The route called Serper and then Tavily, but all three persisted source candidates show `discovered_by=serper` and `found_via=google_organic`, with no enforced diversity or authoritative-source requirement. The routing/selection layer did not convert the relevant query into independent, source-quality-controlled evidence.

Conclusion: `SOURCE_SELECTION + CLAIM_EXTRACTION` are the primary diagnosis, with `SOURCE_CLASSIFICATION + QUERY/ROUTING` contributing. This is not an Evidence relation persistence failure. No relation should be changed in this inspection.

## Handoff state

- Round 1 EvidenceSet v1 remains `draft` and unlocked with its original hash and three Evidence IDs.
- Round 2 EvidenceSet v2 remains `draft` and unlocked with `context_only=8` and `supports=0`.
- NeedHypothesis remains `PROPOSED`.
- ContentExperiment remains `PLANNED / PENDING`.
- ContentCase remains exactly one; ContentRun remains `2`.
- T04.18–T04.23 remain active/not done and T04.24+ remain not started.
- No provider call or Round 3 research should occur before MG CONTENT ENGINE reviews this diagnosis and defines the next repair decision.
