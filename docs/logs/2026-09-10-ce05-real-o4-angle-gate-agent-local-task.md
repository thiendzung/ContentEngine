# CE05 Real O4 Angle Gate — Agent Local Task

## Task identity

```text
TASK ID: CE05-R01-LOCAL
OWNER: Agent Local
OBJECTIVE: execute the real O4 Angle runtime gate and return reviewable evidence without expanding scope.
```

## Base / branch

```text
EXPECTED BASE: latest clean main after the CE05 governance/state-reset PR is merged
BRANCH: create/use only if a small assigned code fix becomes necessary; otherwise verification-only
```

Do not use the historical PR #35 branch as the working source. Fetch GitHub and verify current main first.

## Read first

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/TASK-HARNESS.md`
6. CE05 Journal implementation and the PR #35 runtime bridge code/tests relevant to Angle generation.

## Preconditions

- [ ] governance/state-reset PR is merged to main;
- [ ] local repo fetched/pruned and main fast-forwarded;
- [ ] working tree clean;
- [ ] current gate in `AI_context.MD` is `REAL O4 ANGLE GATE`;
- [ ] application DB and dedicated test DB are clearly distinguished;
- [ ] migration `20260909_0017` is available and approved by the merged repository;
- [ ] locally authenticated approved runner is available;
- [ ] no secret needs to be copied into repository/log output.

If any precondition is false, stop with `BLOCKED`.

## Locked O4 target

```text
Founder framing: How do I know if an original artwork is fairly priced?
ContentOpportunity: 068991ab-de34-4787-9c38-8935c3f0e2da
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
```

Do not change the NeedHypothesis status in this task.

## Scope

1. Verify migration/runtime/settings state required by the merged CE05 Angle runtime.
2. Upgrade the normal application DB only through the already-approved migration path if required for this runtime and if normal migration safety checks pass.
3. Verify the exact active settings/prompt/recipe/model route used for the Angle task.
4. Create the real O4 `ContentRun` through the approved Journal path.
5. Build the real `journal_input_bundle` from the locked O4 inputs.
6. Execute exactly one bounded real Angle generation flow through the merged runtime bridge, allowing only its contract-defined validation retry behavior.
7. Capture the resulting immutable Angle artifact(s), ModelCall provenance and relevant hashes/IDs.
8. Report the generated 3–5 Angle candidates in human-readable form for MG review.
9. Stop. Do not approve an Angle on behalf of Founder and do not start Outline.

## Non-goals

- no T05.10 Outline implementation;
- no VI/EN draft work;
- no new provider/model/agent;
- no prompt architecture redesign;
- no generic abstraction/refactor;
- no EvidenceSet or OriginalityPack mutation;
- no new Discovery/Evidence research unless the existing Angle workflow explicitly fails closed with `RESEARCH_REQUIRED`; if that happens, stop and report;
- no automatic Angle approval;
- no merge.

## Files allowed

Default: `NONE` — this is a runtime/evidence task.

If a small code defect prevents the exact already-approved runtime from operating, stop first and report the defect to MG. Do not patch code unless MG explicitly assigns a bounded fix task.

## Allowed actions

- `git fetch origin --prune`, checkout/pull/inspect commands;
- read repository code/docs/tests;
- inspect migration state;
- run existing migration commands required by the approved repo contract;
- run existing focused tests/probes;
- inspect exact settings/prompt/recipe/model route without exposing secrets;
- execute the existing approved Journal/Angle runtime path;
- read resulting database/artifact/model-call records needed for evidence.

## Execution rule

Use only commands and runtime entrypoints that already exist in the merged repository or are clearly demonstrated by its tests/scripts.

If there is no documented/safe executable path from the merged code to the real Angle flow, do not invent a new script or architecture. Stop with:

```text
BLOCKED: real_angle_runtime_entrypoint_missing
```

and report the exact missing link.

## Required evidence

Report:

- current main commit observed at task start;
- migration state before/after;
- whether normal DB was mutated and exactly by what approved action;
- ContentRun ID;
- `journal_input_bundle` artifact ID/version/hash;
- EvidenceSet ID/version/hash binding;
- OriginalityPack ID/hash binding;
- settings snapshot ID;
- ContextManifest ID;
- prompt key/version and recipe key/version;
- resolved provider/model identity without credentials;
- ModelCall ID/status;
- exact sanitized model-input hash or equivalent persisted binding;
- Angle artifact ID/version/hash;
- number of candidates;
- human-readable text/summary of each candidate;
- focused tests/probes run and result;
- before/after counts for O4 ContentRun / angle artifacts / ModelCall where practical;
- any failure/error code.

Never report API keys, tokens, auth files, environment secrets or raw secret-bearing child process environment.

## Acceptance gates — runtime/data

- [ ] real O4 ContentRun exists through approved path;
- [ ] real `journal_input_bundle` exists;
- [ ] bundle binds the exact locked EvidenceSet and approved OriginalityPack;
- [ ] exact approved settings snapshot/route is used;
- [ ] model call goes through the merged no-tool runtime controls;
- [ ] exact sanitized input provenance/hash is retained;
- [ ] output provenance/hash is retained;
- [ ] 3–5 schema-valid Angle candidates are persisted;
- [ ] no unintended EvidenceSet/OriginalityPack/NeedHypothesis mutation;
- [ ] no unapproved tool/provider capability used.

## Acceptance gates — content evidence for MG review

Agent Local does not decide final content PASS, but evidence must allow MG to verify:

- [ ] candidates are materially different;
- [ ] factual premises are grounded in allowed evidence;
- [ ] no invented MOTGU/business fact;
- [ ] candidates answer the real reader question;
- [ ] no generic AI filler;
- [ ] one candidate could be selected without another infrastructure/code change.

A technically successful call is not enough for final gate PASS.

## Stop conditions

Stop immediately if:

- locked O4 IDs/version/hash do not match;
- migration would require unapproved schema/code;
- active model route/prompt/recipe is missing, ambiguous or stale;
- runtime requests an unapproved capability/tool;
- runtime returns `RESEARCH_REQUIRED` or `BLOCKED` requiring scope expansion;
- data would need destructive/unapproved mutation;
- a secret would need to be exposed;
- no existing safe runtime entrypoint can execute the flow;
- the real generation has completed and evidence has been captured.

Do not approve an Angle, implement Outline, or infer the next task.

## Report format

```text
TASK ID: CE05-R01-LOCAL
START STATE
END STATE
MIGRATION / DB
RUNTIME ROUTE
ARTIFACT / PROVENANCE EVIDENCE
ANGLE CANDIDATES
TESTS / PROBES
UNINTENDED MUTATION CHECK
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, stop and wait for MG review.
