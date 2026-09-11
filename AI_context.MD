# AI_context.MD — ContentEngine current working window

Updated: 2026-09-11

GitHub/repository state is canonical. Detailed history and execution evidence belong in `docs/logs/`.

## Start here

Every agent must synchronize its local repository before reading local task files or executing local code:

```text
git status --porcelain
→ unexpected local changes: STOP / BLOCKED; never auto reset/stash/delete
→ git fetch origin --prune
→ checkout exact assigned ref
→ pull --ff-only
→ require local HEAD == expected remote ref and clean tree
→ read LOCAL AGENTS.md, AI_context.MD, docs/TASKS.md, docs/CHECKLIST.md and exact delegated task
→ execute exact task only
```

Founder owns final merge and final operational content approval.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — FAST OPERATIONAL ACCEPTANCE
CURRENT OUTCOME: get the first real MOTGU Journal package ready for Founder approval on the active runtime database
CURRENT GATE: FRESH EVIDENCE UNBLOCK — IRS + MCI
CURRENT OWNER: Founder merge gate; then Agent Local resumes the same fresh candidate end-to-end
NEXT ACTION: merge the MCI resume task, direct-read the pre-reviewed MCI source once, curate/approve/lock the combined IRS + MCI EvidenceSet, approve the existing originality pack, then continue without stopping to Operational Package V0
BLOCKERS: current fresh EvidenceSet has usable support from only one independent suitable domain (IRS); exact MCI direct-source path exists and is the bounded unblock
HUMAN DECISION REQUIRED: merge the MCI resume task; after successful execution, final operational package/content approval only
```

## Latest fresh runtime evidence

Agent Local executed `CE05-FAST-OPERATIONAL-RESET-LOCAL` from clean merged main `5412f1d1cf621c758abbed6dfb53503eb374ab7d` on `localhost:5432/contentengine` at migration `20260910_0022 (head)`.

Historical lineage probe found no complete compatible non-test database, so runtime resolution is:

`FRESH_ACTIVE_DB`

Locked fresh planning/runtime state:

```text
Project: 00000000-0000-0000-0000-000000000001
NeedHypothesis: 80afc3bb-d768-4cd6-80d5-04f1ef022bc2 / PROPOSED
ContentOpportunity: b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2
ContentExperiment: a34368f1-7f2e-48ae-b598-744de2684417
SettingsSnapshot: 989debbf-5970-44d2-baeb-a605c75e99d6
Settings hash: b2a2993bd4031908140aaa75907d5aa3d2a13dc93b8ec1a4f8e5a6bc8ea54b22
Route: codex_cli / gpt-5.6-luna

EvidenceSet v1: 96c100ce-ae68-46e0-a015-86f65ffe9dc4 / draft
EvidenceSet v2: 3731b791-8a0e-4daa-b079-97fd4e1bf42a / draft
v2 hash: 5d8518428c17b4060b90aadeb86fc0dbdaad0de411ebfe0031012abf06452577
v2: 8 usable supports, all from one IRS source document/domain

Draft OriginalityPack: 4ec19fe4-ebbf-4159-bef3-791bff71eb0a
Founder-authorized usable items: 4

ContentRun: 0
ModelCall: 0
ToolCall: 0
```

The previous task stopped correctly at `BLOCKED_EVIDENCE_QUALITY`: two independent suitable readable source documents/domains were not achieved. Partial fresh state is retained; no historical rows were recreated.

## Bounded evidence unblock

Do not run another broad search pass.

Exact pre-reviewed second source:

`https://mci.si.edu/artifact-appraisals`

This is the Museum Conservation Institute / Smithsonian source already provenance-verified during CE04 and independent from IRS. The repository already contains:

- direct-source runtime: `backend/scripts/run_evidence_source_supplement.py`;
- zero-provider reviewed-existing-source persistence: `backend/scripts/persist_reviewed_existing_evidence.py`;
- historical exact provenance: `docs/logs/2026-09-08-ce04-t04-29-real-provenance.md`.

Exact post-merge resume task:

`docs/logs/2026-09-11-ce05-fast-operational-resume-mci-agent-local-task.md`

Resume rule:

```text
current fresh IRS evidence
→ exactly one direct MCI read
→ require one direct O4 MCI support
→ curate IRS + MCI combined EvidenceSet
→ exact approval + lock
→ approve existing 4-item OriginalityPack
→ Journal run + bundle
→ Angle + pre-authorized checklist selection
→ Outline
→ VI + EN
→ Review/Revise
→ Assertion Audit VI + EN
→ Source-copy VI + EN
→ require NO HARD FAIL
→ Operational Package V0
→ Founder final approval
```

Do not stop after a successful intermediate sub-gate.

## Founder-locked product direction

```text
Question: How do I know if an original artwork is fairly priced?
Audience: first-time art buyer
Angle: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

Keep:

- no universal pricing formula;
- market/context facts separate from personal purchase decisions;
- no invented live artwork/artist/business facts;
- no investment/appreciation, luxury/status, fake scarcity or pressure framing.

## First-operation hard quality policy

Underlying validators remain unchanged.

Hard blockers:

- structural/provenance/hash/lineage corruption;
- fewer than two suitable independent evidence domains after the MCI supplement;
- EvidenceSet not valid/approved/locked;
- OriginalityPack not valid/approved;
- Assertion Audit `fail` or any critical unsupported/contradicted assertion;
- Source-copy `fail_count > 0`;
- unapproved provider/model/tool;
- missing final VI or EN visible content;
- destructive/unbounded mutation or secret exposure.

Non-critical warnings may proceed to Operational Package V0 but must be preserved verbatim for Founder final accept/reject.

No auto-publish is authorized.

## Progress interpretation

For the fresh candidate:

```text
combined IRS + MCI hard evidence gate clean + downstream quality gates clean → T05.15 intent satisfied
Operational Package V0 ready → T05.16 substantively complete
Founder approves package → T05.17 ready for controlled real operation
```

T05.18–T05.22 remain post-operation hardening/metrics/closeout unless an observed safety/data-integrity defect requires earlier action.

## Operating rule after first placement

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION/HARNESS FOR THAT FAILURE MODE
→ RUN AGAIN
```
