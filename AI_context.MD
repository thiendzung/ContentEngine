# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

## Purpose

Shared current-state checkpoint for MG CONTENT ENGINE, Agent Local, and founder.

GitHub is canonical. Detailed history lives in `docs/logs/`; keep this file short and current.

## Agent Local sync rule

Start every task:

```text
git fetch origin --prune
→ checkout task branch
→ git pull --ff-only
→ read AI_context.MD
→ read exact task file under docs/logs/
→ confirm clean working tree
→ execute only assigned scope
```

End every task:

```text
if meaningful canonical state changed → update AI_context.MD
if task requires edits → commit + push
confirm clean working tree
report START HEAD / END HEAD / evidence / blocker / status
```

Do not keep a separate local AI context.

## Roles

MG CONTENT ENGINE owns architecture, core code, important tests, GitHub logs, Gate decisions and Agent Local tasks.

Agent Local owns local sync, Python 3.12, PostgreSQL/migrations, local tests, real provider runs, artifact hashes and bounded edits explicitly assigned by a task.

Founder owns business/product selections and merge decisions.

Never merge automatically.

# Current project state

```text
Project: ContentEngine
Phase: CE04 — Knowledge + Production Research
CE04: ACTIVE

PR-A: CLOSED / MERGED / PASS
PR-B: CLOSED / MERGED / PASS
PR-C: CLOSED / MERGED / PASS
PR-D: CLOSED / MERGED / PASS
PR-E: ACTIVE / DRAFT / EVIDENCE QUALITY GATE ACTIVE
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
Status: DRAFT
```

## Locked O4 input

```text
Founder selection: O4
Question: How do I know if an original artwork is fairly priced?
Planning opportunity: opp_4c397247e40db8ae
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentExperiment: 0551da17-046a-4104-a506-9772680a6133 = PLANNED / PENDING
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5 = exactly one
ContentRun count: 2
```

NeedHypothesis must remain `PROPOSED` in PR-E.

# PR-E contract

```text
Selected ContentOpportunity
→ one legitimate ContentCase
→ Evidence Research
→ Claim extraction
→ Evidence linking
→ supports / contradicts / qualifies / context_only
→ EvidenceSet draft
→ human review
→ lock exact approved EvidenceSet with provider_calls=0
→ OriginalityPack
```

Rules:

- Discovery is not Evidence.
- Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Provider/search rank is not authority.
- Authority must not be inferred from article topic words.
- Community/review, high-commercial-bias and unknown/unverified sources default to `context_only`.
- Automatic claims must be relevant to the selected opportunity subject, not merely share generic research terms.
- Do not weaken relation rules or quality thresholds to obtain `supports`.
- Locked EvidenceSet is immutable; changed research creates a new version.
- OriginalityPack contains MOTGU-owned material only; external web Evidence is excluded.
- No fake ContentRun for standalone Gates.
- No KnowledgeCandidate / Approved Knowledge / Obsidian / CE05 work in PR-E.

# Real Evidence Gate history

## Round 1

```text
Pipeline: PASS
Quality: FAIL
EvidenceSet: 2e423158-42af-4188-9954-90784b8cf37a / v1 / draft / DO NOT LOCK
Reason: factual supports came from one Facebook community thread
```

## Round 2

```text
Pipeline: PASS
Quality: FAIL
Artifact SHA-256: 8c6325822a22c01c76d5f07268b0722540f949e077dbff582b3eddf66ce13a81
EvidenceSet: e9c7f1b9-c812-4ca5-ba36-fdd8af99b8ec / v2 / draft / DO NOT LOCK
Readable SourceDocuments: 3
Evidence: 8
Relations: context_only=8 / supports=0 / contradicts=0 / qualifies=0
research_sufficient: false
stop_reason: bounded_search_exhausted
Diagnosis: SOURCE_SELECTION + CLAIM_EXTRACTION primary; SOURCE_CLASSIFICATION + QUERY/ROUTING contributors
```

## Round 3

```text
Run HEAD: d6e491eadf3aa69920f2b54bc46e3e169c36eca4
CI checked: 34135314608 / PASS
Command count: 1
Provider calls: 4
Artifact SHA-256: f990d972460594dccc8a407e983629774ae2d88d7e659c0b8a5a27aa9e8b1ee4
EvidenceSet: c6d83e7e-663b-4c5a-af13-9b68eb41276c / v3 / draft / DO NOT LOCK
Readable SourceDocuments: 2
Persisted relations: supports=8 / context_only=0 / contradicts=0 / qualifies=0
research_sufficient: true
stop_reason: jina_candidates_exhausted
Persisted support domains: 2
Suitable O4 support domains after human review: 1
Quality: FAIL / BLOCKED
```

Round 3 human review found:

- `museumexchange.com`: one directly useful artwork-appraisal support plus weaker context;
- `dealstream.com`: museum-business valuation, off-scope for original artwork pricing;
- persisted `supports=8` therefore did NOT satisfy the human quality Gate.

# Round 3 diagnosis repair

Root causes:

1. authority false positive — `museum` in an article title/path could make an unrelated domain look institutional;
2. subject drift — generic `valuation/comparable sales/market` overlap could create O4 claims even when the subject was a museum business;
3. Round 3 query included `museum`, encouraging search drift.

Implemented repair:

- authority classification now uses domain identity, not title/path topic words;
- `.edu/.gov` may be strong institutional/low-bias candidates;
- institutional-looking domain names remain candidates but commercial bias stays `unknown` until verified;
- `dealstream.com/.../museums/...` no longer becomes institutional from topic words;
- claim extraction requires both research relevance and selected-question subject relevance;
- for O4, artwork subject matching conservatively covers artwork/artworks/artist/artists/painting/paintings;
- museum-business valuation text is rejected even when it shares valuation keywords;
- source diversity, page-noise filtering and balanced multi-document extraction from Round 2 remain active.

Tests added for the exact Round 3 failure modes.

CI history:

```text
CI #355: FAIL — test import formatting only
CI #356: PASS — full backend/frontend gate
Code checkpoint: 6829d6af7e4ecefd12031dfbc6742962c19cba63
```

Repair log:

`docs/logs/2026-09-07-ce04-pr-e-round3-diagnosis-fix.md`

# Current next action

Run exactly one Round 4 only after the latest branch CI is PASS.

Task:

`docs/logs/2026-09-07-ce04-pr-e-real-gate-round4-task.md`

Round 4 uses a cleaner query with no `museum` term and keeps the same quality threshold.

Minimum human-review Gate:

```text
useful supports >= 2
suitable independent support domains >= 2
exact readable excerpts
claims directly useful to O4
no subject drift
no authority inferred from topic words
no universal pricing formula
no investment/appreciation promise
```

Do not lock v1/v2/v3 or any Round 4 EvidenceSet before MG CONTENT ENGINE review.

Do not tick T04.18–T04.23 and do not start T04.24+.

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
- Record meaningful failures, decisions and lessons under `docs/logs/`.
