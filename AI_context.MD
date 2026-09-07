# AI_context.MD — ContentEngine shared working context

Updated: 2026-09-07

## Purpose

Shared current-state checkpoint for MG CONTENT ENGINE, Agent Local, and founder.

GitHub is canonical. Detailed history lives in `docs/logs/`; this file should stay short and current.

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
- Community/review, high-commercial-bias and unknown/unverified sources default to `context_only`.
- Do not weaken relation rules just to obtain `supports`.
- Locked EvidenceSet is immutable; changed research creates a new version.
- OriginalityPack contains MOTGU-owned material only; web evidence is excluded.
- No fake ContentRun for standalone Gates.
- No KnowledgeCandidate / Approved Knowledge / Obsidian / CE05 work in PR-E.

# Real Gate history

## Round 1

```text
Pipeline: PASS
Evidence quality: FAIL
EvidenceSet: 2e423158-42af-4188-9954-90784b8cf37a / v1 / draft / unlocked
Problem: all factual supports came from one Facebook community thread
Action: DO NOT LOCK v1
```

Loop improvement: community/review and weak sources no longer auto-promote to factual support.

## Round 2

```text
Pipeline: PASS
Evidence quality: FAIL / BLOCKED
Artifact SHA-256: 8c6325822a22c01c76d5f07268b0722540f949e077dbff582b3eddf66ce13a81
EvidenceSet: e9c7f1b9-c812-4ca5-ba36-fdd8af99b8ec / v2 / draft / unlocked
Readable SourceDocuments: 3
Evidence: 8
Relations: context_only=8 / supports=0 / contradicts=0 / qualifies=0
research_sufficient: false
stop_reason: bounded_search_exhausted
OriginalityPack: 8bc23d49-edd4-45c6-99eb-1673d61b4998 / 0 items
```

Round 2 inspection result:

```text
Primary cause 1: SOURCE_SELECTION
Primary cause 2: CLAIM_EXTRACTION
Contributor: SOURCE_CLASSIFICATION
Contributor: QUERY/ROUTING
Potential supports in persisted Round 2 rows: 0
```

Inspection log:

`docs/logs/2026-09-07-ce04-pr-e-round2-evidence-inspection.md`

## Round 3

```text
Run HEAD: d6e491eadf3aa69920f2b54bc46e3e169c36eca4
Latest branch CI: run 34135314608 / PASS
Command count: 1
Provider calls: 4
Artifact: artifacts/research/ce04-evidence-research-v1-20260907T145734Z.json
Artifact SHA-256: f990d972460594dccc8a407e983629774ae2d88d7e659c0b8a5a27aa9e8b1ee4
Artifact size: 3109 bytes
Pipeline: PASS
Evidence quality: FAIL / BLOCKED
EvidenceSet: c6d83e7e-663b-4c5a-af13-9b68eb41276c / v3 / draft / unlocked
Readable SourceDocuments: 2
Evidence: 8
Relations: context_only=0 / supports=8 / contradicts=0 / qualifies=0
research_sufficient: true
stop_reason: jina_candidates_exhausted
Persisted support-source domains: 2
Suitable O4 support-source domains: 1
Quality failure: only one source has a claim directly useful for O4; DealStream rows concern museum valuation, not original artwork pricing
OriginalityPack: 8bc23d49-edd4-45c6-99eb-1673d61b4998 / 0 items
```

Round 3 quality review must not promote the persisted relation count by itself. The
EvidenceSet has two independent persisted domains, but the minimum of two independent
suitable O4 support sources is not met. No universal pricing formula or appreciation
promise was accepted. NeedHypothesis remains `PROPOSED`; v1 and v2 remain draft/unlocked.

# Diagnosis repair

Implemented after Round 2:

- source selection now prefers independent domains before same-domain fill;
- claim extraction rejects page chrome, markdown image/link and short heading-like text;
- query terms participate in claim relevance scoring;
- substantive sentences rank before generic introduction;
- claim extraction balances across readable SourceDocuments instead of letting document 1 consume all quota;
- conservative relation policy remains unchanged.

Regression tests added for source-domain diversity and balanced extraction.

CI #346 failed only on one test line-length lint issue.

CI #347 on head `9a225e30613620d6a650020e26a5e3038f78c3fd`: `PASS` full backend/frontend quality gate.

Repair log:

`docs/logs/2026-09-07-ce04-pr-e-round2-diagnosis-fix.md`

# Current next action

Do not run old Round 1/2 tasks again or rerun Round 3 to force a pass.

Current result:

`BLOCKED — ROUND 3 EVIDENCE QUALITY INSUFFICIENT`

Next action: MG CONTENT ENGINE reviews the Round 3 quality failure and defines a repair
for source relevance/claim extraction before any EvidenceSet lock or T04.18–T04.23 tick.

Minimum quality target before MG review:

```text
supports >= 2
support sources >= 2 independent suitable SourceDocuments/domains
exact readable excerpts
claims directly useful to O4
no universal pricing formula
no investment/appreciation promise
```

Do not lock v1/v2/Round 3, do not change Evidence relations, do not tick T04.18–T04.23, and do not start T04.24+.

# Global rules

- Search is a locator, not factual proof.
- Discovery never silently becomes Evidence.
- Internal MOTGU knowledge is checked before broad external research.
- Provider rank/relevance is not authority.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Do not weaken a Gate to make it green.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
- Record meaningful failures, decisions and lessons under `docs/logs/`.
