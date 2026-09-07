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

Do not curate or lock v1–v5. Their EvidenceSets are historical research outputs, not the final reviewed set.

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

## Next action

Agent Local may run the Smithsonian supplement only after the latest CI for the exact branch head is PASS.

Supplement PASS requires at least one human-reviewed direct O4 support from the locked Smithsonian source with an exact excerpt.

If supplement PASS:

```text
MG reviews exact Smithsonian Evidence IDs
→ combine exact reviewed IRS + Smithsonian Evidence IDs
→ create curated draft EvidenceSet with provider_calls=0
→ final human review
→ lock exact approved set with provider_calls=0
```

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
