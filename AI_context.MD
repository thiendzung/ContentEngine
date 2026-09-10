# AI_context.MD — ContentEngine current working window

Updated: 2026-09-10

GitHub/repository state is canonical. This file contains only the current semantic working window. Detailed history and execution evidence belong in `docs/logs/`.

## Start here

Every agent must synchronize its local repository before reading local task files or executing local code:

```text
git status --porcelain
→ if unexpected local changes: STOP / BLOCKED; do not reset/stash/delete automatically
→ git fetch origin --prune
→ git checkout main (or exact assigned branch)
→ git pull --ff-only origin main when assigned to current main
→ verify HEAD == expected GitHub ref and working tree clean
→ read LOCAL copies of AGENTS.md, AI_context.MD, docs/TASKS.md and exact task log
→ confirm scope + stop conditions
→ execute only the assigned work
```

Do not infer or start the next task. Do not merge unless acting as Founder with explicit intent to merge.

## Current window

```text
PROJECT: ContentEngine
PHASE: CE05 — Journal Engine V1
CURRENT OUTCOME: prove one real MOTGU Journal candidate end-to-end
CURRENT GATE: T05.14 — EN POST-AUDIT CONTENT REMEDIATION
CURRENT OWNER: MG owns contract/review; Agent Local implements only the exact bounded EN post-audit revision task on the assigned PR branch
NEXT ACTION: implement bounded EN-only post-audit revision, merge after CI/review, then run real EN v3 revision + T05.14 re-audit; keep VI PASS immutable
BLOCKERS: no infrastructure blocker known; EN v2 has five unsupported audit findings that must be revised before T05.14 can pass
HUMAN DECISION REQUIRED: none; final content approval remains later
```

## Current progress

- CE01–CE04: CLOSED / PASS.
- CE05 T05.1–T05.10: DONE / MERGED / real gates PASS.
- T05.11/T05.12 bilingual Writer: DONE / real runtime gate PASS.
- T05.13 bounded Review/Revise: DONE / real bilingual gate PASS.
- T05.14 Assertion Audit implementation/recovery/normalization: MERGED through PR #46.
- T05.14 real v3 audit: **VI PASS / EN NEEDS CHANGES**.
- T05.15–T05.22: NOT STARTED.

Dynamic commit/PR/CI state must be read directly from GitHub.

## Locked upstream lineage

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
SOURCE O4 RUN: 43cc7684-c15d-45b2-8de9-dc04777b1808
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / hash 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / hash d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1 / hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
AngleApproval: cebc0f94-77f9-4655-9141-41cd8a5dfc14
SELECTED ANGLE: angle-01
Outline artifact: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / hash 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / hash d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
```

## Locked VI PASS result — do not revise or rerun

```text
VI LocaleVariant: e982a60f-05f0-4e15-9ed3-397db9486dfa
VI Writer run: 1f0b91a7-39d7-449f-84ad-988fd1e8f44e
VI draft v2: a0afa7d0-af3d-4669-ae18-54c54b87731f
VI draft hash: da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85
VI v3 audit eval run: 7cae133b-697c-4ea0-8fff-272077bfbe13
VI v3 audit artifact: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / hash a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI QualityEvaluation: 11dac071-ceef-4204-a1b5-24b8e58ebe0f
VI result: pass
VI unsupported: 0
VI contradicted: 0
```

This PASS is accepted for T05.14. Do not spend another model call on VI unless a later upstream/content change invalidates this exact snapshot.

## Locked EN remediation input

```text
EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN source draft v2: d512f3f4-bc28-473b-9de1-f0a838940191
EN source hash: e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
EN v3 audit eval run: be23b965-3c20-4ea4-88c9-7173e2e72516
EN v3 audit artifact: e89ba535-83d3-48fd-a17d-6150e67a21b2 / v1 / hash e75290894c621f431a51885e1ddc8a7c40cb45bb1cc6dfac8a85917c86f52831
EN QualityEvaluation: 108d887d-639d-4326-846d-1b925005f5e6
EN result: fail
EN unsupported: 5
EN contradicted: 0
EN critical unsupported: 3
EN critical contradicted: 0
```

Exact unsupported findings to remediate:

```text
lead:1 — fact / unsupported / critical
"You cannot tell whether an original artwork is fairly priced from the number alone."

section:understand-price-context:1 — fact / unsupported / critical
"Prices are context-dependent."

section:understand-price-context:3 — interpretation / unsupported / medium
"That helps explain why the price alone is not an objective answer."

section:understand-price-context:4 — fact / unsupported / critical
"It does not establish that a particular artwork is fairly or unfairly priced, and price alone does not prove quality, importance or investment value."

section:ask-for-context:3 — interpretation / unsupported / medium
"These questions invite useful explanation without turning the conversation into a pricing formula."
```

All five must be resolved because Assertion Audit returns `warn` when any unsupported/contradicted assertion remains; the T05.14 acceptance is `audit_result=pass`.

## Remediation contract

Do not call the existing T05.13 Review/Revise CLI against EN v2 as a new cycle. Its `review_revise_en` StepRun/ContextManifest is already completed and must not own a different post-audit revision.

Required implementation:

```text
immutable EN draft v2
+ immutable EN v3 audit FAIL artifact/evaluation
+ exact accepted Outline/EvidenceSet/OriginalityPack
→ new post_audit_revise_en StepRun in the existing EN Writer run
→ new ContextManifest
→ bounded approved no-tool model call
→ model returns only replacements for the exact five failed segments
→ deterministic application to source v2
→ non-target visible copy remains byte-identical
→ exact support refs / section structure remain unchanged
→ full canonical Writer validation
→ immutable EN journal_draft v3
→ exact rerun reuses v3 with zero model calls
```

The model must not rewrite the whole article. The implementation should bind findings from the persisted audit artifact/evaluation, not from caller-provided free text.

Preferred generator:

`ce05.journal_post_audit_revision.v1`

Preferred registry task:

`post_audit_revise_en`

A narrow registry-only migration `20260910_0022` is acceptable if required.

Exact implementation task:

`docs/logs/2026-09-10-ce05-t05-14-en-post-audit-revision-agent-local-task.md`

## Post-merge real sequence

```text
sync clean main
→ verify locked VI PASS + EN v2/audit FAIL input
→ apply/verify post-audit registry migration if present
→ EN v2 → bounded EN v3 revision
→ exact revision rerun = reuse / zero model calls
→ Assertion Audit v3 against exact EN v3
→ exact EN audit rerun = reuse / zero model calls
→ if EN pass and unsupported/contradicted = 0: T05.14 PASS
→ only then activate T05.15
```

Do not rerun VI. Do not start T05.15 before EN passes.

## Operating constraints

- WIP: one primary implementation task + at most one delegated local verification task.
- No new provider, agent, generic framework, architecture redesign or automated publishing before ONE REAL JOURNAL PASS unless a proven blocker requires it.
- No new research or EvidenceSet expansion for this remediation; unsupported broad statements must be removed/recast rather than backfilled with convenient evidence.
- Source drafts/audits and all upstream lineage remain immutable.
- Dynamic truth: Git/GitHub owns HEAD, PR, CI and branch state.
- `ModelCall.result_artifact_id` linkage remains post-T05.17 hardening unless it becomes blocking.
