# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

GitHub is canonical. Detailed history lives in `docs/logs/`; keep this file short and current.

## Agent Local rule

Start every task:

```text
git fetch origin --prune
→ checkout assigned branch
→ git pull --ff-only
→ read AI_context.MD
→ read exact assigned task in docs/logs/
→ confirm clean tree
→ execute only assigned scope
```

End every task:

```text
if meaningful canonical state changed → update AI_context.MD
if task requires edits → commit + push
confirm clean tree
report START HEAD / END HEAD / evidence / blocker / status
```

Never merge automatically.

# Current state

```text
Project: ContentEngine
Phase: CE04 — Knowledge + Production Research
CE04: ACTIVE

PR-A: CLOSED / MERGED / PASS
PR-B: CLOSED / MERGED / PASS
PR-C: CLOSED / MERGED / PASS
PR-D: CLOSED / MERGED / PASS
PR-E: ACTIVE / DRAFT
PR-F: NOT STARTED

T04.1–T04.17: DONE
T04.18–T04.23: ACTIVE / NOT DONE
T04.24–T04.31: NOT STARTED
```

Current PR:

```text
PR #28 — CE04 PR-E — Evidence Research + Evidence Set
Branch: ce04-evidence-research-evidence-set
Base main: a52052adde3cf19889098013fd5065f86cab62fb
Status: OPEN / DRAFT
```

# Locked O4

```text
Founder framing: How do I know if an original artwork is fairly priced?
Planning label: Artsy prices
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Need statement: A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.
ContentExperiment: 0551da17-046a-4104-a506-9772680a6133 = PLANNED / PENDING
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5 = exactly one
ContentRun count: 2
```

NeedHypothesis must remain `PROPOSED` in PR-E.

# PR-E contract

```text
selected opportunity
→ one legitimate ContentCase
→ Evidence Research
→ Claim extraction
→ Evidence linking
→ human review
→ curated EvidenceSet from exact reviewed Evidence IDs, provider_calls=0
→ final review
→ lock exact approved EvidenceSet, provider_calls=0
→ OriginalityPack
```

Locked rules:

- Discovery/Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Search/provider rank is not authority.
- `.gov` / `.edu` only create institutional candidates; claim-level human review is still required.
- Evidence subject is anchored to `NeedHypothesis.statement`, not `Artsy prices`.
- Community/review/high-commercial/unknown-unverified sources do not auto-promote to supports.
- Do not weaken thresholds to make a Gate pass.
- Locked EvidenceSet is immutable.
- OriginalityPack contains MOTGU-owned material only.
- No fake ContentRun, KnowledgeCandidate, Approved Knowledge, Obsidian, CE05, or T04.24+ work in PR-E.

# Retained human Gate state

Round 5 IRS Evidence remains the only useful retained support set:

```text
EvidenceSet v5: 32199d87-5114-4ac6-9bd5-6f4151bd0c7c / draft / unlocked
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
```

Required Gate:

```text
useful supports >= 2
suitable independent domains >= 2
```

Do not curate or lock v1–v7. They are historical draft outputs.

# Smithsonian American Art result

Locked URL:

`https://americanart.si.edu/research/my-art/object-worth`

First direct-source run:

- Jina read succeeded;
- 8 Evidence were navigation/page-chrome;
- human useful support = 0;
- v6 remained draft/unlocked.

Page-chrome repair:

- reject Markdown-image fragments;
- reject segments with 2+ Markdown links;
- regression test: `backend/tests/test_ce04_smithsonian_page_chrome.py`;
- final-head CI #383 / run `34143040018` = PASS.

Same-source rerun:

```text
Run HEAD: 6eaa398e3c2deee07c6d4489150c7420c63c4897
Artifact: artifacts/research/ce04-evidence-source-supplement-v1-20260907T162753Z.json
SHA-256: e1e16b62ff39404aa55d4b98b1fc37470cf17e6455fabf659f350de76634ac52
SourceDocument: 84c34963-a7c4-5f4d-9c0f-3632ff8cab41
Claims: 0
Evidence: 0
DIRECT_O4_SUPPORT: 0
Combined Gate: 3 useful supports / 1 suitable independent domain
Result: BLOCKED — SMITHSONIAN RERUN INSUFFICIENT
```

Do not run this URL again.

# MCI direct-source Gate

MG CONTENT ENGINE pre-reviewed and locked one replacement source:

`https://mci.si.edu/artifact-appraisals`

Reason:

- Museum Conservation Institute / Smithsonian;
- page directly discusses monetary value of artworks;
- states fixed values are difficult to establish;
- states prices asked/offered depend on seller/purchaser interests and market trends;
- advises checking current sales and auction price ranges;
- independent from `irs.gov`;
- source selection is not Evidence approval.

Exact task:

`docs/logs/2026-09-07-ce04-pr-e-mci-direct-source-task.md`

Boundary:

```text
run exactly once
Serper=0
Tavily=0
Exa=0
Jina=1
Search/Discovery=0
no code edit during Gate
no relation mutation
no curation/lock
no ContentRun/KnowledgeCandidate
T04.18–T04.23 remain NOT DONE
T04.24+ remain NOT STARTED
PR #28 remains DRAFT
```

MCI run:

```text
Run HEAD: 9f1a80950408cc878ebf32d4b3eb104cce479df3
Latest branch CI: run 34143838987 / PASS
Command count: 1
Artifact: artifacts/research/ce04-evidence-source-supplement-v1-20260907T163734Z.json
SHA-256: 029ec3b1b278b8326bd0398afca9d420659db041f007d4d496324ddc99261b8a
Artifact size: 1437 bytes
Provider calls: Serper=0 / Tavily=0 / Exa=0 / Jina=1
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a / mci.si.edu
EvidenceSet: 4e29998b-2c61-4a49-83c7-765813d0a0c1 / v7 / draft / unlocked
Evidence: 2 / Claims: 2 / relations: supports=2 / context_only=0 / contradicts=0 / qualifies=0
Human review: DIRECT_O4_SUPPORT=0 / useful supports=0 / suitable domains=0
Combined Gate with IRS: useful supports=3 / suitable independent domains=1
Result: BLOCKED — MCI DIRECT-SOURCE INSUFFICIENT
```

Human review of both exact readable excerpts:

```text
0b78a9da-00a9-49c7-90cf-dc06f3345876 / f7e3bc71-2740-43c4-8613-4c19660c8818 / supports / document_sentence:93 / excerpt match=true / WEAK/OFF_SCOPE — describes appraisals for accepted donations, not how a buyer evaluates price
27088478-755a-498f-a89d-de4bdc178023 / f4c3032c-c44a-410d-89d0-33f68167771c / supports / document_sentence:105 / excerpt match=true / WEAK/OFF_SCOPE — bibliography entry, not O4 valuation guidance
```

The MCI source produced no direct O4 support. The existing v1–v7 EvidenceSets remain
draft/unlocked; no relation was manually changed, and no curation or lock occurred.

# MCI SourceDocument inspection

```text
Inspection HEAD: 6cd23ed3d942de39fa24579d90edeb2e4d6da818
Provider calls: 0
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a / https://mci.si.edu/artifact-appraisals
content_chars: 8497 / segments: 1 / keyword_hits: 1
Diagnosis: EXTRACTOR_MISS
Direct O4 support passages found in stored content: 1
Claim/Evidence/EvidenceSet created: 0
Database mutation: 0
```

The oversized `SEGMENT 1` contains direct O4 body prose: artwork values are not fixed,
asking/offered prices depend on seller and purchaser interests and market trends, and
current ranges can be checked against sales and auctions. Exact reviewed excerpt:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

This is `DIRECT_O4_SUPPORT` at SourceDocument inspection level. Directory, contact,
service-description, disclaimer, and bibliography material in the same segment remains
`WEAK/OFF_SCOPE`. The reader stored the relevant prose; automatic extraction missed it.

# Current next action

Do not rerun MCI or read another URL. MG CONTENT ENGINE may review the exact direct prose
and decide whether to persist it as reviewed Evidence. Do not curate or lock an EvidenceSet
in this inspection task; v1–v7 remain draft/unlocked.

Current inspection result: `EXTRACTOR_MISS`.

# Global rules

- Search is a locator, not factual proof.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Record meaningful decisions/failures under `docs/logs/`.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
