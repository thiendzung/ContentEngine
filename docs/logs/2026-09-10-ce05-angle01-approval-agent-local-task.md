# CE05 Angle-01 Approval Persistence — Agent Local Task

## Task identity

```text
TASK ID: CE05-R01-APPROVE-LOCAL
OWNER: Agent Local
OBJECTIVE: persist and verify the Founder-selected angle-01 against the exact real O4 Angle artifact, without starting Outline.
```

## Base / branch

```text
EXPECTED BASE: latest clean main after the angle-01 approval-handoff PR is merged
BRANCH: none required; runtime/database task only
```

## Read first

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/TASK-HARNESS.md`
6. `docs/logs/2026-09-10-ce05-real-o4-angle-selection.md`
7. `backend/scripts/approve_angle_candidate.py`
8. `backend/app/modules/content_engine/journal/angle.py` approval/handoff contract

## Preconditions

- [ ] approval-handoff PR is merged to main;
- [ ] local repo fetched/pruned and main fast-forwarded;
- [ ] working tree clean;
- [ ] `AI_context.MD` current gate is `ANGLE-01 APPROVAL PERSISTENCE`;
- [ ] migration remains `20260909_0017 (head)`;
- [ ] ContentRun `43cc7684-c15d-45b2-8de9-dc04777b1808` exists and is the real O4 run;
- [ ] run is still waiting for Angle approval / no Outline has started;
- [ ] Angle artifact `854d4f34-22c0-4a9e-8d00-0f7f9461036d` is version `1` with exact hash `e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe`;
- [ ] artifact still contains `angle-01` with working title `A First-Time Buyer’s Checklist for Understanding an Artwork’s Price`;
- [ ] zero existing AngleApproval rows for this Angle artifact;
- [ ] EvidenceSet v8 remains locked and exact;
- [ ] OriginalityPack remains approved and exact;
- [ ] NeedHypothesis remains `PROPOSED`;
- [ ] no secret needs to be copied into output/logs.

If any precondition is false, stop with `BLOCKED`.

## Locked Founder decision

```text
SELECTED ANGLE: angle-01
APPROVED BY: founder
APPROVAL REASON: Founder selected angle-01 after MG Real O4 review; use the practical first-time-buyer checklist direction as the primary Journal angle.
```

Do not alter this decision text or substitute another candidate.

## Exact runtime target

```text
ContentRun: 43cc7684-c15d-45b2-8de9-dc04777b1808
journal_input_bundle: abaffbbb-9d7a-4c7c-af8c-d28b79ee3991 / v1
bundle hash: 894e608b640bf4d3e67de8a4e7f94991d7637ca3c0392de1d00c1966c234cd3b
Angle artifact: 854d4f34-22c0-4a9e-8d00-0f7f9461036d / v1
Angle artifact hash: e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe
Selected angle: angle-01
```

## Scope

1. Verify the exact preconditions above read-only.
2. Run the approved production CLI exactly once to persist the Founder decision.
3. Capture the returned AngleApproval ID and selected candidate hash.
4. Confirm `handoff_verified=true` from the CLI; this proves the approved-angle boundary resolves the same exact artifact/candidate snapshot.
5. Run the exact same command a second time to prove terminal idempotency; it must return the same AngleApproval ID and selected candidate hash and must not create a second approval.
6. Verify relevant before/after row counts and locked upstream state.
7. Report evidence and stop.

## Exact command

From the repository `backend/` directory, using the same approved local Python environment used for ContentEngine:

```bash
python scripts/approve_angle_candidate.py \
  --angle-artifact-id 854d4f34-22c0-4a9e-8d00-0f7f9461036d \
  --expected-artifact-version 1 \
  --expected-artifact-hash e49941402aed35b5714c1367ab1c7c0864b111aaca782e446f3cb280332f94fe \
  --selected-angle-id angle-01 \
  --approved-by founder \
  --approval-reason "Founder selected angle-01 after MG Real O4 review; use the practical first-time-buyer checklist direction as the primary Journal angle."
```

Run that exact command twice only after all preconditions pass.

## Non-goals

- no model/provider call;
- no new ContentRun;
- no new Angle generation;
- no selection of another Angle;
- no Outline generation or T05.10 implementation/execution;
- no VI/EN draft;
- no EvidenceSet/OriginalityPack/NeedHypothesis mutation;
- no repository edit;
- no architecture/refactor;
- no merge.

## Files allowed

`NONE` for modification. Repository is read-only for this task.

## Required evidence

Report:

- main commit at start;
- migration before/after;
- ContentRun ID/status before/after;
- Angle artifact ID/version/hash;
- candidate count and selected angle ID/title;
- AngleApproval count before/after;
- created/reused AngleApproval ID;
- selected candidate hash returned by the CLI;
- `approved_by` and approval reason;
- `handoff_verified` value;
- second-run approval ID/hash and idempotency verdict;
- ContentRun / Artifact / ModelCall / ToolCall counts before/after;
- EvidenceSet state before/after;
- OriginalityPack state before/after;
- NeedHypothesis state before/after;
- any error code.

Never expose secrets or environment credentials.

## Acceptance gates

- [ ] exactly one AngleApproval exists for the exact Angle artifact;
- [ ] selected angle is exactly `angle-01`;
- [ ] persisted artifact ID/version/hash exactly match the locked target;
- [ ] persisted selected candidate hash matches the validated `angle-01` snapshot;
- [ ] `approved_by=founder`;
- [ ] approval reason exactly matches this task;
- [ ] CLI reports `handoff_verified=true`;
- [ ] second identical command returns the same approval ID and candidate hash;
- [ ] no second approval row is created;
- [ ] no model/provider/tool call is added;
- [ ] no new ContentRun or Angle artifact is added;
- [ ] EvidenceSet unchanged;
- [ ] OriginalityPack unchanged;
- [ ] NeedHypothesis remains `PROPOSED`;
- [ ] no Outline work starts.

## Stop conditions

Stop immediately if:

- artifact ID/version/hash differs;
- `angle-01` is absent or title/snapshot is inconsistent;
- an existing approval conflicts with the locked Founder decision;
- migration/runtime state is unexpected;
- any upstream locked input changed;
- the CLI or approved-angle handoff fails;
- persistence succeeds and all required evidence is captured.

Do not repair or overwrite a conflicting approval. Report `BLOCKED`.

## Report format

```text
TASK ID: CE05-R01-APPROVE-LOCAL
START STATE
END STATE
ANGLE SNAPSHOT
APPROVAL RESULT
HANDOFF VERIFICATION
IDEMPOTENCY
UPSTREAM IMMUTABILITY
COUNTS / SIDE EFFECTS
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, stop. Do not start T05.10.