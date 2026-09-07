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

## Locked O4

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
→ supports / contradicts / qualifies / context_only
→ EvidenceSet draft
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
- Only `.gov` / `.edu` auto-become strong institutional evidence candidates.
- Other unverified domains remain discovery/context until reviewed.
- Evidence subject is anchored to `NeedHypothesis.statement`, not `Artsy prices`.
- Community/review/high-commercial/unknown-unverified sources do not auto-promote to supports.
- Do not weaken thresholds to make a Gate pass.
- Locked EvidenceSet is immutable.
- OriginalityPack contains MOTGU-owned material only; web Evidence is excluded.
- No fake ContentRun, KnowledgeCandidate, Approved Knowledge, Obsidian, CE05, or T04.24+ work in PR-E.

# Evidence Gate history

```text
Round 1: FAIL — v1 draft; one Facebook thread supplied supports.
Round 2: FAIL — v2 draft; source selection + claim extraction failed.
Round 3: FAIL — v3 draft; museum-business subject drift created false-looking supports.
Round 4: FAIL — v4 draft; only one suitable support domain.
Round 5: FAIL — v5 draft; 3 useful IRS supports but only one suitable independent domain.
```

Round 5 retained human-reviewed IRS support:

```text
EvidenceSet v5: 32199d87-5114-4ac6-9bd5-6f4151bd0c7c / draft / unlocked
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
```

Do not lock or treat v1–v6 as the final curated EvidenceSet.

# Smithsonian direct-source supplement

Broad search is stopped. Direct-source path reads one human-reviewed URL using Jina only:

```text
backend/app/modules/research/evidence/direct_source.py
backend/scripts/run_evidence_source_supplement.py
backend/tests/test_ce04_direct_source_evidence.py
```

Locked source:

`https://americanart.si.edu/research/my-art/object-worth`

First supplement run:

```text
Run HEAD: 805e66b39b4f21279372b4d93744385df3b4301c
Artifact: artifacts/research/ce04-evidence-source-supplement-v1-20260907T161142Z.json
SHA-256: 158493ac24a7a5d3b49dc547febac088daf0de569ef55854ca02761ae51c2965
Provider calls: Serper=0 / Tavily=0 / Exa=0 / Jina=1
SourceDocument: 5224a365-cfc1-5ed0-9354-8ed9e1626ee2
EvidenceSet: 295d57f1-678e-4f33-912f-3e993fe59dfe / v6 / draft / unlocked
Persisted Evidence: 8 / supports=8
Human review: 0 useful supports
Combined Gate with IRS: 3 useful supports / 1 suitable independent domain
Result: BLOCKED — SMITHSONIAN SUPPLEMENT INSUFFICIENT
```

Human review found all 8 v6 rows were navigation/page-chrome despite exact excerpt matches.

# Smithsonian page-chrome rerun

```text
Run HEAD: 6eaa398e3c2deee07c6d4489150c7420c63c4897
Latest branch CI: run 34143040018 / PASS
Command count: 1
Source: https://americanart.si.edu/research/my-art/object-worth
Artifact: artifacts/research/ce04-evidence-source-supplement-v1-20260907T162753Z.json
Artifact SHA-256: e1e16b62ff39404aa55d4b98b1fc37470cf17e6455fabf659f350de76634ac52
Artifact size: 1281 bytes
Provider calls: Serper=0 / Tavily=0 / Exa=0 / Jina=1
SourceDocument: 84c34963-a7c4-5f4d-9c0f-3632ff8cab41 / americanart.si.edu
Claims: 0 / Evidence: 0 / EvidenceSet: none
Human review: DIRECT_O4_SUPPORT=0 / useful supports=0 / suitable domains=0
Combined Gate with IRS: useful supports=3 / suitable independent domains=1
Result: BLOCKED — SMITHSONIAN RERUN INSUFFICIENT
```

The page-chrome regression test passed (`1 passed`): the extractor rejects `Collection
Highlights`, `Search Artworks`/`Search Artists`, Markdown image fragments, and the
`Latinx Art`/`20th Century`/`Asian American Art` navigation-image patterns. The rerun
produced no new Claim/Evidence row, so no direct O4 support survived for review. Existing
v1–v6 EvidenceSets remain unchanged and draft/unlocked; no relation was manually changed.

# Page-chrome fix

Root cause: multi-link navigation and embedded Markdown images contained many `artwork/artist` terms and could outrank real body prose.

Implemented:

- reject any claim candidate containing Markdown image syntax `![`;
- reject any claim candidate containing two or more Markdown links;
- preserve prose with at most one inline link;
- keep authority, subject anchor and quality threshold unchanged.

Regression test:

`backend/tests/test_ce04_smithsonian_page_chrome.py`

Canonical log:

`docs/logs/2026-09-07-ce04-pr-e-smithsonian-page-chrome-fix.md`

Code/test checkpoint:

```text
service fix commit: b8ef2143b4adb111285cea0a2678b189c2164300
regression test commit: d1d5da6b985a3405ff853939ead5f68d23182b9a
CI #380: backend lint/types/migration/tests PASS; final workflow completion must be verified before rerun.
```

# Current next action

Do not rerun the Smithsonian supplement again and do not read another URL. MG CONTENT
ENGINE must review the failed rerun and decide the next approved action.

Required boundary:

- Serper=0 / Tavily=0 / Exa=0;
- Jina=1;
- no Search/Discovery;
- no code edit during Gate;
- no relation mutation;
- no curation or lock;
- no ContentRun/KnowledgeCandidate;
- T04.18–T04.23 remain NOT DONE;
- T04.24+ remain NOT STARTED.

The combined human Gate remains below `2 useful supports / 2 suitable independent domains`:
IRS contributes `3 / 1`, and this rerun contributes `0 / 0`. Do not curate or lock an
EvidenceSet.

Current result: `BLOCKED — SMITHSONIAN RERUN INSUFFICIENT`.

# Global rules

- Search is a locator, not factual proof.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Record meaningful decisions/failures under `docs/logs/`.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
