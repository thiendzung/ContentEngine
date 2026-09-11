# CE05 — Fast Operational Resume via MCI — Agent Local Task

Date: 2026-09-11

## TASK ID

`CE05-FAST-OPERATIONAL-RESUME-MCI-LOCAL`

## OWNER

Agent Local executes. MG has pre-reviewed the MCI source choice and the evidence-combination rule below. Founder retains final operational content approval.

## OBJECTIVE

Resume the already-started fresh CE05 operational candidate from its real evidence blocker. Add exactly one suitable independent Smithsonian/MCI source through the existing direct-source path, curate/approve/lock a combined IRS + MCI EvidenceSet, approve the already-created Founder-authorized OriginalityPack, then continue the merged fast-operational task through Operational Package V0 without another successful-subgate stop.

Do not restart Discovery or broad Evidence Research. Do not recreate the fresh planning spine.

## BASE / SYNC

Execute only after the PR containing this task is merged.

Start from clean synchronized `main`:

```bash
git status --porcelain
```

Unexpected changes => `BLOCKED`; never auto reset/stash/delete/overwrite.

Then:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require HEAD == origin/main and clean.

Read local copies:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/logs/2026-09-11-ce05-fast-operational-reset.md`
6. `docs/logs/2026-09-11-ce05-fast-operational-reset-agent-local-task.md`
7. this task
8. `docs/logs/2026-09-08-ce04-t04-29-real-provenance.md`
9. `docs/logs/2026-09-07-ce04-pr-e-mci-direct-source-task.md`

## LOCKED FRESH STATE

Revalidate before mutation:

```text
Project: 00000000-0000-0000-0000-000000000001
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
ContentOpportunity: b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2
ContentExperiment: a34368f1-7f2e-48ae-b598-744de2684417
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6
Settings hash: b2a2993bd4031908140aaa75907d5aa3d2a13dc93b8ec1a4f8e5a6bc8ea54b22
Route: codex_cli / gpt-5.6-luna

Existing EvidenceSet v1: 96c100ce-ae68-46e0-a015-86f65ffe9dc4 / draft
Existing EvidenceSet v2: 3731b791-8a0e-4daa-b079-97fd4e1bf42a / draft
v2 hash: 5d8518428c17b4060b90aadeb86fc0dbdaad0de411ebfe0031012abf06452577
v2 reviewed usable support shape: 8 supports, all from one IRS source document/domain

Existing draft OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a
Expected usable items: 4 Founder-authorized items

ContentRun / ModelCall / ToolCall before resume: 0 / 0 / 0
```

Resolve the ContentCase belonging to the exact fresh opportunity. Require exactly one ContentCase with:

- project above;
- `content_opportunity_id = b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2`;
- `need_hypothesis_id = 80afc3bb-d768-4cd6-80d5-04f1ef022bc2`;
- `content_type = journal`.

Record its ID and reuse it for all remaining work.

If the exact fresh state is missing/ambiguous or the v2 hash changed unexpectedly, stop `BLOCKED`.

## STEP 1 — ONE DIRECT MCI READ, NO SEARCH

The exact second independent source is pre-reviewed:

`https://mci.si.edu/artifact-appraisals`

This is Museum Conservation Institute / Smithsonian and is independent from the current IRS source.

Run exactly once from repo root, substituting no IDs:

```bash
backend/.venv/bin/python backend/scripts/run_evidence_source_supplement.py \
  --source-url "https://mci.si.edu/artifact-appraisals" \
  --query "How do I know if an original artwork is fairly priced?" \
  --opportunity-id "b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2" \
  --need-id "80afc3bb-d768-4cd6-80d5-04f1ef022bc2" \
  --project "motgu" \
  --locale "en" \
  --country "us" \
  --max-claims 8
```

Expected provider boundary:

```text
Search/Discovery = 0
Serper = 0
Tavily = 0
Exa = 0
Jina direct read = 1
```

Require one readable SourceDocument whose canonical URL is the exact MCI URL above.

Human-review every new MCI Evidence row. Reject navigation, appraiser directories, contact lists, product/service endorsements, investment framing, universal formulas, and off-scope collectible-only material.

A `DIRECT_O4_SUPPORT` must help establish one of these bounded points:

- fixed monetary values for artworks/collectibles are difficult to establish;
- asking/offered prices depend on buyer/seller interests and market trends;
- current sale/auction ranges can provide market context.

Do not treat those as a universal consumer valuation formula.

### Reviewed-existing-source fallback

If the MCI SourceDocument is read successfully but automatic extraction yields no clean direct O4 support, do NOT run another provider/search pass.

Use the existing zero-provider CLI exactly once:

`backend/scripts/persist_reviewed_existing_evidence.py`

Persist one `supports` Evidence from that exact MCI SourceDocument using the exact historical sentence already preserved and provenance-verified in:

`docs/logs/2026-09-08-ce04-t04-29-real-provenance.md` → `Candidate 1 — MCI / Smithsonian` → `Exact excerpt`.

Requirements:

- `--content-case-id` = resolved fresh ContentCase;
- `--source-document-id` = newly read MCI SourceDocument;
- `--statement` and `--excerpt` = the exact verified sentence from that section, copied without paraphrase;
- `--relation supports`;
- `--reviewed-by "MG CONTENT ENGINE"`.

Before persistence, require the exact excerpt to be present in the newly stored SourceDocument content. If it is absent, stop `BLOCKED_MCI_SOURCE_CONTENT_CHANGED`.

At the end of Step 1 require at least one MCI `DIRECT_O4_SUPPORT` Evidence with exact excerpt-source match.

## STEP 2 — CURATE ONE COMBINED IRS + MCI EVIDENCESET

Do not modify v1, v2 or any supplement EvidenceSet.

From v2, take the exact eight already-reviewed usable IRS `supports` Evidence IDs reported by the prior task. Revalidate that each:

- belongs to the fresh ContentCase/project;
- relation = `supports`;
- resolves to the same readable IRS source document/domain;
- excerpt exists in its SourceDocument;
- does not introduce investment/appreciation or universal-formula claims.

Add exactly one strongest MCI `DIRECT_O4_SUPPORT` Evidence from Step 1.

Create/reuse a new combined draft EvidenceSet with the existing CLI:

```text
backend/scripts/curate_evidence_set.py
```

using the resolved fresh ContentCase and the nine selected Evidence IDs.

Require:

```text
supports >= 9
readable source documents >= 2
independent suitable domains >= 2
required domains represented: irs.gov + mci.si.edu
status = draft before approval
```

If the direct MCI extraction produced multiple good supports, still include only the single strongest directly relevant MCI Evidence in this first operational set. Keep the package small.

Record combined EvidenceSet ID/version/hash and member IDs.

## STEP 3 — APPROVE AND LOCK THE COMBINED EVIDENCESET

Use the existing `approve_evidence_set()` service through a temporary stdin/one-off Python invocation from `backend/`; do not create a repository file.

Bind the exact combined EvidenceSet ID, version and recomputed content hash.

Use:

```text
approved_by = MG CONTENT ENGINE
approval_reason = Fresh CE05 operational evidence gate: reviewed IRS plus independent MCI support.
```

Record the EvidenceSetApproval ID.

Then use the existing CLI:

```bash
.venv/bin/python -m scripts.lock_evidence_set \
  --evidence-set-id <combined-id> \
  --locked-by "MG CONTENT ENGINE" \
  --approval-id <approval-id>
```

Require exact approval binding and final `status = locked`.

Run no second research pass.

## STEP 4 — APPROVE THE EXISTING FOUNDER-AUTHORIZED ORIGINALITYPACK

Do not create new originality items.

Load exactly:

`4ec19fe4-ebbf-4159-bef3-791bff71eb0a`

Require:

- belongs to resolved fresh ContentCase;
- status is still `draft`;
- exactly four usable Founder-authorized items from the original fast task;
- no content/item mutation since creation.

Use existing `originality_pack_snapshot_hash()` + `approve_originality_pack()` through a temporary stdin/one-off Python invocation from `backend/`; do not create a repo file.

Use:

```text
approved_by = Founder
approval_reason = Founder-authorized four-item guardrail pack for CE05 fast operational acceptance.
```

Require final status `approved` and exact stored snapshot hash == recomputed snapshot hash.

## STEP 5 — CONTINUE THE ORIGINAL FAST OPERATIONAL SPRINT

After Steps 1–4 PASS, continue immediately from the first Journal ContentRun / `journal_input_bundle` step through the remaining merged task:

`docs/logs/2026-09-11-ce05-fast-operational-reset-agent-local-task.md`

Use the fresh IDs produced/validated in this resume task, especially the new locked combined EvidenceSet and approved OriginalityPack.

Continue without stopping through:

```text
Journal ContentRun + journal_input_bundle
→ Angle generation
→ pre-authorized checklist-direction selection + AngleApproval
→ Outline
→ VI + EN Writers
→ Review/Revise
→ Assertion Audit VI + EN
→ Source-copy VI + EN
→ require NO HARD FAIL
→ Operational Package V0 JSON + Markdown + SHA-256
```

All Founder-locked angle/product guardrails and hard quality rules from the original fast task remain unchanged.

This task supersedes only the earlier two-broad-research-pass stop condition. It does not weaken any downstream validator.

## HARD BLOCKERS

Stop only for:

- fresh-state/hash/lineage mismatch;
- MCI direct source cannot be read or verified;
- exact MCI reviewed excerpt no longer exists in the newly read source document;
- combined EvidenceSet cannot prove at least two suitable independent domains;
- EvidenceSet approval/lock binding failure;
- OriginalityPack approval/snapshot failure;
- structural/provenance/hash corruption downstream;
- Assertion Audit result `fail` or any critical unsupported/contradicted assertion;
- Source-copy `fail_count > 0`;
- unapproved provider/model/tool;
- missing final visible VI/EN content;
- destructive/unbounded mutation or secret exposure.

Non-critical warnings are preserved in Operational Package V0 and do not create a new pre-operation micro-task.

## FORBIDDEN

- no Discovery rerun;
- no broad Search Evidence Research pass;
- no `asia.si.edu` retry;
- no `wcc.art` retry;
- no new source-selection exploration if the exact MCI source succeeds;
- no application code change;
- no migration;
- no validator threshold change;
- no historical UUID recreation;
- no new provider/model/agent;
- no auto-publish;
- no T05.18–T05.22 work.

## REQUIRED REPORT

Return one combined report:

```text
TASK ID: CE05-FAST-OPERATIONAL-RESUME-MCI-LOCAL
START STATE
FRESH STATE REVALIDATION
RESOLVED CONTENTCASE
MCI DIRECT SOURCE
  command count
  provider counts
  SourceDocument ID/hash/url
  Evidence IDs + verdicts
  reviewed-existing-source fallback used? yes/no
COMBINED IRS + MCI EVIDENCESET
  member Evidence IDs
  source document IDs/domains
  ID/version/hash
  Approval ID
  locked status
ORIGINALITY PACK
  ID/hash/status/approver
JOURNAL RUN / BUNDLE / ROUTE
ANGLE + PRE-AUTHORIZED SELECTION
OUTLINE / WRITERS / REVIEW-REVISE
VI ASSERTION AUDIT
EN ASSERTION AUDIT
VI SOURCE-COPY
EN SOURCE-COPY
SURVIVING WARNINGS
OPERATIONAL PACKAGE V0
  JSON path / SHA-256 / bytes
  Markdown path / SHA-256 / bytes
  deterministic reserialization check
HARD-GATE SUMMARY
SIDE EFFECT / IMMUTABILITY CHECK
RISKS / BLOCKERS
STATUS: READY FOR FOUNDER OPERATIONAL APPROVAL | BLOCKED
```

Paste complete final VI and EN visible content when package-ready.

## STOP POLICY

Do not stop after successful MCI, EvidenceSet, OriginalityPack, Journal, Angle, Outline, Writer, Review, Audit or Source-copy substeps.

Stop only at the first hard blocker or when Operational Package V0 is ready for Founder approval.

NO SELF-DIRECTED NEXT TASK.
