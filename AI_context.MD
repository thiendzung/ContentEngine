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
→ legitimate ContentCase
→ Evidence Research
→ Claim/Evidence links
→ human review
→ reviewed-existing-source correction when extractor misses stored prose
→ curated EvidenceSet from exact reviewed Evidence IDs, provider_calls=0
→ final review
→ lock exact approved EvidenceSet, provider_calls=0
→ OriginalityPack
```

Locked rules:

- Discovery/Search snippets are not factual Evidence.
- External Evidence requires readable source content + exact locator/excerpt.
- Search/provider rank is not authority.
- `.gov/.edu` create institutional candidates only; claim-level human review is still required.
- Evidence subject is anchored to `NeedHypothesis.statement`, not `Artsy prices`.
- Community/review/high-commercial/unknown-unverified sources do not auto-promote to supports.
- Do not weaken thresholds to make a Gate pass.
- Locked EvidenceSet is immutable.
- OriginalityPack contains MOTGU-owned material only.
- No fake ContentRun, KnowledgeCandidate, Approved Knowledge, Obsidian, CE05, or T04.24+ work in PR-E.

# Retained reviewed Evidence

Round 5 IRS retained:

```text
EvidenceSet v5: 32199d87-5114-4ac6-9bd5-6f4151bd0c7c / draft / unlocked
Useful supports: 3
Suitable independent domains: 1 — www.irs.gov
Evidence IDs:
- ae930468-0760-4e6c-b0d6-8346f5119912
- e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
- fe1e11c2-1250-4c4a-ba50-0174b7b514bd
```

Required human Gate:

```text
useful supports >= 2
suitable independent domains >= 2
```

Do not lock v1–v7. They are historical draft research outputs.

# MCI diagnosis

MCI source:

`https://mci.si.edu/artifact-appraisals`

Stored SourceDocument:

`f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a`

Direct-source automatic extraction produced two off-scope Evidence rows, but zero-provider SourceDocument inspection proved the reader stored direct O4 prose.

Diagnosis:

`EXTRACTOR_MISS`

Exact human-reviewed sentence:

> Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.

Verdict:

`DIRECT_O4_SUPPORT`

Do not reread MCI or call another provider.

# Reviewed-existing-source path

Implemented:

```text
backend/app/modules/research/evidence/reviewed_source.py
backend/scripts/persist_reviewed_existing_evidence.py
backend/tests/test_ce04_reviewed_existing_source.py
```

Contract:

- existing persisted SourceDocument only;
- human reviewer required;
- exact excerpt must exist in stored SourceDocument;
- ContentCase/source project must match;
- Claim remains `unverified`;
- create/reuse new Evidence; never mutate old automatic Evidence;
- provenance method = `human_review_existing_source`;
- `human_reviewed=true` + reviewer stored in metadata;
- same input is idempotent;
- provider calls = 0;
- no EvidenceSet creation or lock.

Canonical decision:

`docs/logs/2026-09-07-ce04-pr-e-reviewed-existing-source-decision.md`

Real persistence task:

`docs/logs/2026-09-07-ce04-pr-e-reviewed-mci-evidence-persistence-task.md`

Code/test checkpoint:

```text
Reviewed path final code/test HEAD: 4fb4ae1d2c8de81a809580a045a99bbcfb3f7510
CI #396 / run 34145294793: PASS full backend + frontend gate
```

# Reviewed MCI Evidence

```text
Claim: 70f7c72b-f23a-4528-8c03-79583e45e59a / status=unverified
Evidence: 5e97ed0d-8989-47d3-af4e-b2f29a5110cd / relation=supports
SourceDocument: f77b9e62-42c5-5a06-aa8b-6505ef3b6b3a
Excerpt: Prices asked and amounts offered are determined by personal interests of both the seller and the purchaser and by the trends in the market.
Excerpt match: true
Human review: true / reviewer=MG CONTENT ENGINE
Provenance: method=human_review_existing_source
Provider calls: 0
```

The reviewed-existing-source link does not mutate the three previous MCI Evidence rows,
create an EvidenceSet, or lock one. Combined with the retained IRS supports, the human
Gate is `4 useful supports / 2 suitable independent domains`.

# Current next action

EvidenceSet v8 is now locked after MG CONTENT ENGINE approval. Any next work, including
OriginalityPack, requires a separate explicitly scoped task.

Boundary:

```text
Serper=0
Tavily=0
Exa=0
Jina=0
Search/Discovery=0
no URL open
no relation mutation
EvidenceSet v8 locked; do not mutate it
no ContentRun/KnowledgeCandidate
T04.18–T04.23 remain NOT DONE
T04.24+ remain NOT STARTED
PR #28 remains DRAFT
```

The reviewed MCI Evidence verifies correctly; combined IRS + MCI human Gate reaches the
required second independent domain. EvidenceSet v8 is immutable after this lock.

# Curated EvidenceSet v8 checkpoint

```text
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / version=8 / status=locked / locked=true
Locked by: MG CONTENT ENGINE
Evidence IDs:
- ae930468-0760-4e6c-b0d6-8346f5119912
- e4c31ee7-0627-4dcc-8e2a-db2ab8269b45
- fe1e11c2-1250-4c4a-ba50-0174b7b514bd
- 5e97ed0d-8989-47d3-af4e-b2f29a5110cd
Relation counts: supports=4
SourceDocument count: 2
Provider calls: 0
MG CURATION REVIEW: PASS
```

The exact four reviewed Evidence IDs are now in one new curated draft. No Evidence,
relation, or historical EvidenceSet was changed. The exact curated draft is now locked
and must not be mutated.

# Production OriginalityPack builder code checkpoint

The Production OriginalityPack builder now supports structured MOTGU-owned material in the
existing `item_refs_json` column without a migration. A usable item must retain the exact
structured object with:

```text
type=motgu_owned_material
source_ref
material
writer_use
guardrails
approval_ref
```

Legacy ref-only inputs are normalized to `type=reference_only` and do not count as usable
originality material. Empty material text, incomplete items and Evidence references do not
close the originality gap. External IRS/MCI Evidence is excluded, duplicate items are
deduped deterministically, and the same normalized input reuses the existing non-retired
pack. `originality_item_count` reports usable items only.

Code/test checkpoint:

```text
backend/scripts/curate_originality_pack.py
backend/tests/test_originality_pack_builder.py
provider calls: 0
real DB mutation: 0
EvidenceSet v8: unchanged
T04.18–T04.23: ACTIVE / NOT DONE
T04.24+: NOT STARTED
```

The builder CLI was added for a later explicitly scoped curation action and was not run in
this code/test task. Any task that changes a meaningful canonical state must update
`AI_context.MD` with the observed result and preserved boundaries.

# Global rules

- Search is a locator, not factual proof.
- Raw provider output is not Approved Knowledge.
- Live artwork price/availability stays canonical in WordPress/WooCommerce.
- Secrets stay env/local only.
- No hidden retry or infinite provider fallback.
- Record meaningful decisions/failures under `docs/logs/`.
- Do not begin the next PR slice before current PR merge + post-merge clean checkpoint.
