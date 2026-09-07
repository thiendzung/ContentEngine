# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

## Purpose

Short current-state checkpoint for MG CONTENT ENGINE, Agent Local, and founder.
GitHub is canonical. Detailed history stays under `docs/logs/`.

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

Do not keep a separate local AI context. Never merge automatically.

# Current project state

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

## Locked O4 input

```text
Founder framing: How do I know if an original artwork is fairly priced?
Planning label/question: Artsy prices
Planning opportunity: opp_4c397247e40db8ae
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
Need statement: A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.
ContentExperiment: 0551da17-046a-4104-a506-9772680a6133 = PLANNED / PENDING
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5 = exactly one
ContentRun count: 2
```

NeedHypothesis must stay `PROPOSED` in PR-E.

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
→ final human review
→ lock exact approved EvidenceSet, provider_calls=0
→ OriginalityPack
```

Rules:

- Discovery is not Evidence.
- Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Search/provider rank is not authority.
- Authority is not inferred from title/path or brand words in a hostname.
- Only strong automatic public/academic domain signals (`.gov`, `.edu`) auto-become institutional evidence candidates.
- Other unverified domains remain discovery/context candidates until reviewed.
- Evidence subject is anchored to `NeedHypothesis.statement`, not the Discovery label `Artsy prices`.
- Community/review, high-commercial-bias, and unknown/unverified sources do not auto-promote to factual support.
- Do not weaken thresholds to obtain `supports`.
- Locked EvidenceSet is immutable; changed Evidence creates a new version.
- OriginalityPack contains MOTGU-owned material only; web Evidence is excluded.
- No fake ContentRun for standalone Gates.
- No KnowledgeCandidate / Approved Knowledge / Obsidian / CE05 work in PR-E.

# Evidence Gate history

```text
Round 1: FAIL — v1 draft; supports came from one Facebook thread.
Round 2: FAIL — v2 draft; context_only=8, supports=0; source selection + claim extraction were primary blockers.
Round 3: FAIL — v3 draft; persisted supports included museum-business subject drift.
Round 4: FAIL — v4 430966fb-b143-4179-a017-7875e54a4914 draft; supports=1, context_only=5; only one useful support domain.
```

Do not lock or curate v1–v4 as production EvidenceSets. Their stored source metadata/relation may predate the final conservative authority contract.

## Round 4 repair

Agent Local repair:

`6a968b2e0e5dd7631f46439b6065ec1c1e0d0a5a`

Accepted:

- subject anchor uses `NeedHypothesis.statement`;
- `backend/scripts/curate_evidence_set.py` is zero-provider, draft-only, idempotent for same Evidence IDs, and versions changed IDs;
- no Evidence/relation mutation and no lock in curation;
- CI #363 PASS on the Agent Local repair head.

MG follow-up tightened authority further:

- non-`.gov/.edu` domains do not auto-become institutional merely because the hostname contains `museum`, `archive`, `association`, `institute`, etc.;
- regression coverage added for `.org`, `.net`, `.io`, `.edu`, `.gov`;
- CI #365 exposed one legacy test expecting `examplemuseum.org = institutional`; classifier was kept strict and the old assertion was updated to the new contract.

Repair review log:

`docs/logs/2026-09-07-ce04-pr-e-round4-repair-review.md`

# Current next action

Do not curate old Evidence yet and do not rerun Round 4.

Run exactly one authority-targeted Round 5 only after the latest branch CI is PASS:

`docs/logs/2026-09-07-ce04-pr-e-real-gate-round5-task.md`

Round 5 query is locked to strong source families:

```text
artwork appraisal fair market value condition provenance comparable sales (site:irs.gov OR site:si.edu)
```

Minimum human Gate:

```text
useful supports >= 2
suitable independent support domains >= 2
exact readable excerpts
claims directly useful to O4
no subject drift
no authority inferred from naming words
no universal pricing formula
no investment/appreciation promise
```

If Round 5 passes:

```text
human review exact Evidence IDs
→ curate draft EvidenceSet with provider_calls=0
→ review curated draft
→ lock exact approved set with provider_calls=0
```

Until then:

- T04.18–T04.23 remain NOT DONE;
- T04.24+ remain NOT STARTED;
- v1–v4 remain draft/unlocked;
- PR #28 remains DRAFT.

# Global rules

- Search is a locator, not factual proof.
- Discovery never silently becomes Evidence.
- Internal MOTGU knowledge is checked before broad external research.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Do not weaken a Gate to make it green.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
- Record meaningful failures, decisions, and lessons under `docs/logs/`.
