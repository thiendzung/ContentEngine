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
PR-E: ACTIVE / DRAFT / BLOCKED ON EVIDENCE QUALITY
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

# Round 4

```text
Run HEAD: fffedad27cddfee2e93489f7838204adb2f8692d
Latest branch CI: run 34137280517 / PASS
Command count: 1
Provider calls: 4
Artifact: artifacts/research/ce04-evidence-research-v1-20260907T151810Z.json
Artifact SHA-256: aaba83a7119ebb656c545186b146df5146082c143b9c847ae1c1523c01047949
Artifact size: 3055 bytes
Pipeline: PASS
Evidence quality: FAIL / BLOCKED
EvidenceSet: 430966fb-b143-4179-a017-7875e54a4914 / v4 / draft / unlocked
Readable SourceDocuments: 3
Evidence: 6
Relations: context_only=5 / supports=1 / contradicts=0 / qualifies=0
research_sufficient: true
stop_reason: serper_sufficient
Unique readable domains: 3
Useful O4 support domains after human review: 1
Quality failure: only one useful support was found; the other five rows remain context_only
OriginalityPack: 8bc23d49-edd4-45c6-99eb-1673d61b4998 / 0 items
```

Round 4 source review found two topic-relevant domains (`www.artworkarchive.com`
and `appraisily.com`) plus `www.museumexchange.com`; only the Artwork Archive FMV
definition is a direct O4 support. Appraisily rows are relevant context but remain
`context_only` because source authority/bias is unknown; Museum Exchange was read but
produced no Round 4 Evidence. Therefore the human Gate count is `1 useful support / 1
suitable support domain`, below the required `2 / 2`. No universal pricing formula or
investment/appreciation promise was accepted.

# Round 4 repair

```text
Repair base HEAD: 3a204cd331c7c01221b279a22fc91300f988ee76
Subject anchor: NeedHypothesis.statement; planning question is not the Evidence subject
Source classification: brand .com domains are not institutional from hostname words alone
Curation: backend/scripts/curate_evidence_set.py / provider calls=0 / draft only / no Evidence or relation mutation / no lock
Regression scope: subject extraction, source classification, and zero-provider EvidenceSet curation
Targeted checks: ruff PASS / mypy PASS / 29 pytest PASS
Full pytest: 35 failed, 136 passed — asyncpg event-loop isolation failures plus one unrelated telemetry assertion
Provider calls in repair: 0
Evidence quality state: FAIL / BLOCKED / v4 draft / unlocked
```

# Current next action

Current result:

`BLOCKED — ROUND 4 EVIDENCE QUALITY INSUFFICIENT`

MG CONTENT ENGINE must review the repair boundary and the six Round 4 Evidence rows before
any human curation. The curation helper accepts only already-reviewed Evidence IDs and
creates a draft EvidenceSet for separate review and lock.
Do not rerun Round 4, lock v1/v2/v3/v4, change relations, tick T04.18–T04.23, or start
T04.24+.

NeedHypothesis remains `PROPOSED`; ContentExperiment remains `PLANNED / PENDING`; PR #28
remains `OPEN / DRAFT`.

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

Any task that changes an important repository or workflow state must update this file in
the same task.

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
