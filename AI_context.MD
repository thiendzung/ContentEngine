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

Rules:

- Discovery/Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Search/provider rank is not authority.
- Authority is not inferred from title/path or brand words in hostnames.
- Only `.gov` / `.edu` auto-become strong institutional evidence candidates.
- Other unverified domains remain discovery/context until reviewed.
- Evidence subject is anchored to `NeedHypothesis.statement`, not `Artsy prices`.
- Community/review/high-commercial/unknown-unverified sources do not auto-promote to supports.
- Do not weaken thresholds to make a Gate pass.
- Locked EvidenceSet is immutable.
- OriginalityPack contains MOTGU-owned material only; web Evidence is excluded.
- No fake ContentRun, KnowledgeCandidate, Approved Knowledge, Obsidian, CE05, or T04.24+ work in PR-E.

# Gate history

```text
Round 1: FAIL — v1 draft; one Facebook thread supplied supports.
Round 2: FAIL — v2 draft; supports=0; source selection + claim extraction failed.
Round 3: FAIL — v3 draft; museum-business subject drift produced false-looking supports.
Round 4: FAIL — v4 draft; only 1 suitable support domain.
Round 5: FAIL — v5 32199d87-5114-4ac6-9bd5-6f4151bd0c7c draft/unlocked.
```

Round 5 details:

```text
Artifact: artifacts/research/ce04-evidence-research-v1-20260907T155341Z.json
SHA-256: 61eef344d5997b1b85be036016c5a91b2823fa34df608ca38a47498ed7f971f2
Evidence: 8
Relations: supports=3 / context_only=5
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
Result: BLOCKED — ROUND 5 EVIDENCE QUALITY INSUFFICIENT
```

Do not curate or lock v1–v6. Their EvidenceSets are historical research outputs, not the final reviewed set.

# Current repair / supplement

Broad search is stopped. The missing item is one second strong independent support domain.

MG CONTENT ENGINE added a narrow direct-source path:

```text
backend/app/modules/research/evidence/direct_source.py
backend/scripts/run_evidence_source_supplement.py
backend/tests/test_ce04_direct_source_evidence.py
```

Boundary:

- exactly one human-reviewed URL;
- Serper/Tavily/Exa = 0 calls;
- Jina = 1 read;
- result reuses canonical ProductionResearchResult + EvidenceResearchWorkflow;
- no relation mutation;
- no lock;
- no fake ContentRun.

Locked Smithsonian source:

`https://americanart.si.edu/research/my-art/object-worth`

Canonical review:

`docs/logs/2026-09-07-ce04-pr-e-round5-review.md`

Assigned task:

`docs/logs/2026-09-07-ce04-pr-e-smithsonian-supplement-task.md`

# Smithsonian supplement

```text
Run HEAD: 805e66b39b4f21279372b4d93744385df3b4301c
Command count: 1
Source: https://americanart.si.edu/research/my-art/object-worth
Artifact: artifacts/research/ce04-evidence-source-supplement-v1-20260907T161142Z.json
Artifact SHA-256: 158493ac24a7a5d3b49dc547febac088daf0de569ef55854ca02761ae51c2965
Artifact size: 1965 bytes
Provider calls: Serper=0 / Tavily=0 / Exa=0 / Jina=1
SourceDocument: 5224a365-cfc1-5ed0-9354-8ed9e1626ee2 / americanart.si.edu
EvidenceSet: 295d57f1-678e-4f33-912f-3e993fe59dfe / v6 / draft / unlocked
Evidence: 8 / Claims: 8 / relations: supports=8 / context_only=0 / contradicts=0 / qualifies=0
Excerpt match: 8/8 exact in the readable SourceDocument
Human review: DIRECT_O4_SUPPORT=0 / useful supports=0 / suitable domains=0
Combined with reviewed IRS Evidence: useful supports=3 / suitable independent domains=1
Result: BLOCKED — SMITHSONIAN SUPPLEMENT INSUFFICIENT
```

All eight generated claims are navigation/page-chrome links rather than valuation claims;
they are marked `WEAK/OFF_SCOPE` despite exact excerpt matches:

```text
44101787-7281-486e-9f83-89f5a5bbe24a / 5e8e7c2e-083c-4527-be29-d7f8df39f835 / supports / document_sentence:24 / WEAK/OFF_SCOPE
610f0b5e-ce56-4dfd-90f0-c76ae5800836 / dcb03371-99d0-4646-8813-b7f6de15198d / supports / document_sentence:33 / WEAK/OFF_SCOPE
75154a5f-a643-469d-8810-ea8ea7d52872 / 478a0651-6d0c-4317-a1d4-2503f510ea73 / supports / document_sentence:30 / WEAK/OFF_SCOPE
81ed1f8b-815c-4a73-9fca-085b09ac1bd4 / 771deb9c-eafa-432e-823b-335dd224abd6 / supports / document_sentence:202 / WEAK/OFF_SCOPE
a1af30ba-9276-4f50-93ab-51aeccad6433 / 56fa5e7c-9489-4b3d-817d-5b23093bcc88 / supports / document_sentence:22 / WEAK/OFF_SCOPE
bedeeb7c-5116-49d9-b9dc-38f8b127b780 / 43e3491d-1cc2-4b08-828e-76b2e4313eb4 / supports / document_sentence:204 / WEAK/OFF_SCOPE
ec64704d-d26a-41ae-be90-f3da9a514791 / 8f9faf8b-d6ec-4e5d-bd39-837a4c3197d4 / supports / document_sentence:201 / WEAK/OFF_SCOPE
f397d86d-3a64-4c77-bd05-4965e3345188 / 47e0cc08-dc98-49b1-8eb4-d330d0cccc3a / supports / document_sentence:31 / WEAK/OFF_SCOPE
```

## Next action

Do not rerun the supplement and do not read another URL. The Smithsonian supplement failed
to add a direct O4 support. MG CONTENT ENGINE must review the eight rows before any
curation decision.

The combined human Gate remains below `2 useful supports / 2 suitable independent domains`:
the three IRS supports provide one suitable domain, while Smithsonian provides zero useful
supports. Do not curate or lock v6 yet.

Until then:

- T04.18–T04.23 remain NOT DONE;
- T04.24+ remain NOT STARTED;
- no EvidenceSet is locked;
- PR #28 remains DRAFT.

# Global rules

- Search is a locator, not factual proof.
- Internal MOTGU knowledge is checked before broad external research.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Record meaningful decisions/failures under `docs/logs/`.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
