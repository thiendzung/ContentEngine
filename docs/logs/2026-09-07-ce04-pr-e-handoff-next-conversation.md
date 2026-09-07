# HANDOFF — CE04 PR-E → NEXT CONVERSATION

Updated: 2026-09-07

## 1. PURPOSE

This file is the canonical handoff for continuing `ContentEngine` in a new conversation.

Use this priority order when state differs:

1. GitHub current branch/PR HEAD.
2. `AI_context.MD` on that exact HEAD.
3. Exact task log under `docs/logs/`.
4. Older logs / conversation history.

Do not continue from memory alone.

---

## 2. REPOSITORY STATE

```text
Repository: thiendzung/ContentEngine
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
Current checkpoint before this handoff log: 5b5fd8a73fe18d5861127a8b8071655f0ef33021
CI #398 / run 34145838998: PASS
PR: OPEN / DRAFT / MERGEABLE
```

Creating this handoff log advances the branch HEAD. The next conversation must fetch the live PR HEAD and verify CI again before executing a state-changing task.

---

## 3. LOCKED O4 INPUT

Founder-selected content direction:

`How do I know if an original artwork is fairly priced?`

Canonical IDs:

```text
ContentOpportunity:
068991ab-de34-4787-9c38-8935c3f0e2da

NeedHypothesis:
530bdd27-f008-4910-9b3b-df83e007cfa2
Status: PROPOSED

Need statement:
A first-time art buyer wants to understand whether an original artwork price makes sense before deciding to buy.

ContentExperiment:
0551da17-046a-4104-a506-9772680a6133
Status: PLANNED / PENDING

ContentCase:
9ec6133b-5f14-46d0-9866-e3b049e537b5
Exactly one for O4.

ContentRun count:
2
```

PR-E must not promote the NeedHypothesis.

---

## 4. PR-E CONTRACT

```text
selected ContentOpportunity
→ one legitimate ContentCase
→ Evidence Research
→ Claim/Evidence candidates
→ human review
→ reviewed-existing-source correction when extractor misses stored prose
→ curated EvidenceSet from exact reviewed Evidence IDs
→ final human review
→ explicit lock of exact reviewed EvidenceSet
→ OriginalityPack readiness
```

PR-E does NOT include:

- T04.24+ Knowledge Candidate / Approved Knowledge;
- Obsidian admission;
- CE05 outline/draft;
- WordPress publishing;
- automatic NeedHypothesis promotion;
- new provider;
- generic workflow-engine expansion.

---

## 5. LOCKED EVIDENCE RULES

1. Discovery/Search snippets are not factual Evidence.
2. External Evidence requires successfully read content + exact locator + excerpt.
3. Search/provider rank is never authority.
4. `.gov/.edu` only create stronger source candidates; claim-level human review is still required.
5. Community/review/high-commercial/unverified sources do not auto-become factual supports.
6. Evidence subject is anchored to `NeedHypothesis.statement`, not the planning label `Artsy prices`.
7. Prefer missing Evidence over confident weak Evidence.
8. Do not weaken thresholds to make a Gate pass.
9. Locked EvidenceSet is immutable.
10. OriginalityPack contains MOTGU-owned material only.
11. No fake ContentRun.
12. Do not create KnowledgeCandidate or start T04.24+ inside PR-E.

---

## 6. WHAT HAPPENED IN REAL EVIDENCE RESEARCH

### Round 1

Pipeline worked but all factual-looking support came from one Facebook community thread.

Decision:

`PIPELINE PASS / EVIDENCE QUALITY FAIL`

Lesson:

community/review sources must remain context by default.

### Round 2

```text
supports=0
context_only=8
```

Diagnosis:

`SOURCE_SELECTION + CLAIM_EXTRACTION`

### Round 3

Source diversity improved, but the system misread topical words such as `museum` as authority and allowed subject drift.

Fixes:

- authority no longer inferred from title/path/brand words;
- subject matching anchored to the actual Need;
- `.com/.org/.net/...` do not auto-become institutional from names.

### Round 4

Topic quality improved but still only one useful support domain.

### Round 5

IRS produced strong reviewed Evidence.

Human Gate result:

```text
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
```

Retained IRS Evidence IDs:

```text
ae930468-0760-4e6c-b0d6-8346f5119912
e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
fe1e11c2-1250-4c4a-ba50-0174b7b514bd
```

### Smithsonian American Art direct-source attempt

First run read navigation/page-chrome as Evidence.

Fix:

- reject Markdown-image fragments;
- reject segments with 2+ Markdown links;
- regression test added.

Same-source rerun produced:

```text
Claims: 0
Evidence: 0
```

The URL was closed. Do not retry.

### MCI direct-source attempt

Source:

`https://mci.si.edu/artifact-appraisals`

Stored SourceDocument:

`f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`

Automatic extractor created only off-scope rows.

Zero-provider SourceDocument inspection found direct O4 prose already stored:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

Diagnosis:

`EXTRACTOR_MISS`

This proved that another provider call was unnecessary.

---

## 7. REVIEWED-EXISTING-SOURCE PATH

Implemented:

```text
backend/app/modules/research/evidence/reviewed_source.py
backend/scripts/persist_reviewed_existing_evidence.py
backend/tests/test_ce04_reviewed_existing_source.py
```

Contract:

- uses an already persisted SourceDocument;
- requires explicit human reviewer;
- exact excerpt must exist in stored SourceDocument;
- validates ContentCase/project/source boundaries;
- Claim stays `unverified`;
- creates/reuses a new Evidence row;
- never mutates old automatic Evidence;
- provenance method = `human_review_existing_source`;
- stores `human_reviewed=true` and reviewer;
- idempotent for same input;
- provider calls = 0;
- does not create or lock EvidenceSet.

Code/test checkpoint:

```text
4fb4ae1d2c8de81a809580a045a99bbcfb3f7510
CI #396 / run 34145294793: PASS
```

Reviewed MCI persistence result:

```text
Claim:
70f7c72b-f23a-4528-8c03-79583e45e59a
status=unverified

Evidence:
5e97ed0d-8989-47d3-af4e-b2f29a5110cd
relation=supports

SourceDocument:
f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a

Excerpt match: true
Human reviewed: true
Reviewer: MG CONTENT ENGINE
Provider calls: 0
```

Combined human Gate now reaches:

```text
Useful supports: 4
Suitable independent domains: 2
Domains: irs.gov + mci.si.edu
Gate requirement: >=2 supports / >=2 domains
STATUS: PASS
```

Research must STOP here. No more provider calls are justified for PR-E.

---

## 8. HISTORICAL EVIDENCESETS

v1–v7 are research-history drafts.

They must remain:

`draft / unlocked`

Do NOT lock v1–v7.

Known checkpoints include:

```text
v5:
32199d87-5114-4ac6-9bd5-6f4151bd0c7c

v6:
295d57f1-678e-4f33-912f-3e993fe59dfe

v7:
4e29998b-2c61-4a49-83c7-765813d0a0c1
```

The final EvidenceSet must be a NEW curated draft built only from exact human-reviewed Evidence IDs.

---

## 9. IMMEDIATE NEXT ACTION

No Search.
No provider.
No URL read.

Create one curated draft EvidenceSet from exactly these four reviewed Evidence IDs:

```text
ae930468-0760-4e6c-b0d6-8346f5119912
e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
fe1e11c2-1250-4c4a-ba50-0174b7b514bd
5e97ed0d-8989-47d3-af4e-b2f29a5110cd
```

ContentCase:

`9ec6133b-5f14-46d0-9866-e3b049e537b5`

Use:

`backend/scripts/curate_evidence_set.py`

Expected boundary:

```text
provider_calls=0
status=draft
supports=4
source_document_count>=2
NeedHypothesis remains PROPOSED
ContentExperiment remains PLANNED / PENDING
ContentRun count unchanged
KnowledgeCandidate remains 0
no lock in the curation task
```

Suggested exact command after verifying current HEAD + CI:

```bash
backend/.venv/bin/python backend/scripts/curate_evidence_set.py \
  --content-case-id 9ec6133b-5f14-46d0-9866-e3b049e537b5 \
  --evidence-id ae930468-0760-4e6c-b0d6-8346f5119912 \
  --evidence-id e4c31ee7-0627-4dcc-8e2a-db2ab8269b45 \
  --evidence-id fe1e11c2-1250-4c4a-ba50-0174b7b514bd \
  --evidence-id 5e97ed0d-8989-47d3-af4e-b2f29a5110cd
```

Then STOP and return the curated EvidenceSet ID/version/status for MG CONTENT ENGINE review.

Do NOT lock in the same task.

---

## 10. AFTER CURATED DRAFT PASSES REVIEW

Run the separate lock command only against the exact reviewed EvidenceSet ID:

```bash
backend/.venv/bin/python backend/scripts/lock_evidence_set.py \
  --evidence-set-id "<EXACT_REVIEWED_EVIDENCE_SET_ID>" \
  --locked-by "MG CONTENT ENGINE"
```

Expected:

```text
provider_calls=0
same EvidenceSet ID/version
status=locked
NeedHypothesis=PROPOSED
ContentExperiment=PLANNED / PENDING
ContentRun unchanged
KnowledgeCandidate=0
```

No provider rerun is allowed during lock.

---

## 11. PR-E FINALIZATION AFTER LOCK

Only after curated draft review + exact lock PASS:

1. synchronize Data Contract wording so Evidence relations include `qualifies`;
2. update `README.md` if current state section requires it;
3. update `AGENTS.md`;
4. update `docs/TASKS.md`;
5. update CE04 phase plan/runbook if applicable;
6. update `AI_context.MD`;
7. create final PR-E closeout log;
8. mark T04.18–T04.23 DONE only when all Gate evidence is recorded;
9. keep T04.24–T04.31 NOT STARTED;
10. run final-head CI;
11. only after final-head CI PASS mark PR #28 Ready for Review;
12. founder/user merges manually;
13. run separate post-merge closeout/verification;
14. only then begin PR-F / T04.24–T04.31.

Assistant must not merge unless founder explicitly asks.

---

# OPTIMIZED WORKING PROCESS V2

## A. Canonical truth order

Always resolve state in this order:

```text
GitHub live HEAD
→ AI_context.MD on exact HEAD
→ exact assigned task log
→ older logs
→ chat memory
```

Never act from chat memory when GitHub can answer the question.

## B. One task = one state transition

Every Agent Local task must have exactly one main purpose, for example:

```text
inspect
OR persist reviewed Evidence
OR curate EvidenceSet
OR lock EvidenceSet
OR final sync
```

Do not combine research + curation + lock in one task.

## C. Diagnose before another provider call

After a real Evidence Gate fails:

```text
FAIL
→ inspect persisted SourceDocument / DB first
→ determine SOURCE_GAP vs EXTRACTOR_MISS vs CLASSIFIER_ERROR vs CLAIM_QUALITY
→ fix/operate on the exact cause
→ only then consider another external call
```

Never repeatedly rerun research to force PASS.

## D. Automatic extraction is candidate generation only

Machine `supports` is not human-approved support.

Always use:

```text
machine candidate
→ exact excerpt check
→ source suitability check
→ human verdict
→ reviewed persistence/curation
```

Human Gate outranks raw relation counts.

## E. Reuse stored evidence before rereading the web

If a SourceDocument already exists:

```text
inspect stored content first
→ use reviewed-existing-source path if exact prose exists
→ do not call Jina/Search again
```

This reduces cost, drift and noise.

## F. Provider budget discipline

Default rule for PR-E from this checkpoint:

`provider_calls = 0`

Any new external call requires a new explicit diagnosis showing that stored evidence cannot satisfy the Gate.

## G. Two-stage EvidenceSet control

Never auto-lock a research-generated set.

Required flow:

```text
reviewed Evidence IDs
→ curated draft
→ human review
→ separate exact lock
```

Locked set is immutable.

## H. Agent Local task template

Every task should include:

```text
GOAL
EXPECTED START HEAD
PRECONDITIONS
EXACT ALLOWED COMMANDS
FILES ALLOWED TO CHANGE
PROVIDER BUDGET
STOP RULES
INVARIANTS
AI_context update rule
REPORT SCHEMA
PASS STATUS
FAIL STATUS
```

At start:

```text
git fetch origin --prune
checkout branch
pull --ff-only
read AI_context.MD
read exact task
confirm HEAD
confirm clean tree
confirm CI when required
```

At end:

```text
if canonical state changed → update AI_context.MD
commit/push only assigned files
confirm clean tree
report START HEAD / END HEAD / evidence / blocker / status
```

## I. Conversation handoff discipline

When moving to a new conversation, paste this handoff first.

The new assistant should NOT immediately implement anything.

First it must:

1. fetch PR #28 current metadata;
2. verify live branch HEAD;
3. read `AI_context.MD` at that exact HEAD;
4. compare against this handoff;
5. inspect latest CI;
6. state the exact next action;
7. only then modify repo or issue Agent Local instructions.

## J. No premature phase advance

Do not begin PR-F until:

```text
PR-E curated set PASS
→ lock PASS
→ docs sync PASS
→ final-head CI PASS
→ PR #28 Ready
→ founder merge
→ post-merge verification PASS
```

---

## 12. NEXT CONVERSATION STARTING PROMPT

Paste the full handoff, then ask the assistant to:

```text
Đọc handoff này và kiểm tra trạng thái GitHub hiện tại trước.
Không gọi provider.
Không merge.
Không bắt đầu T04.24+.
Mục tiêu gần nhất là review trạng thái Evidence đã duyệt và, nếu repo vẫn đúng checkpoint, tạo task curate EvidenceSet draft từ đúng 4 Evidence ID IRS + MCI, provider_calls=0.
Sau mỗi thay đổi trạng thái quan trọng phải cập nhật AI_context.MD.
```

---

## 13. STATUS AT HANDOFF

```text
CE04: ACTIVE
PR #28: OPEN / DRAFT
PR-E CORE: PASS
REAL RESEARCH: STOP
HUMAN EVIDENCE GATE: PASS — 4 useful supports / 2 suitable domains
CURATED FINAL EVIDENCESET: NOT YET CREATED
FINAL LOCK: NOT YET DONE
T04.18–T04.23: ACTIVE / NOT DONE
T04.24+: NOT STARTED
NEXT: ZERO-PROVIDER CURATED DRAFT
```
