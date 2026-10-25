# AGENT LOCAL TASK — CONTENT_PRODUCTION_V1_RC1_VERIFY

## Goal

Verify the exact Content Production v1 RC1 candidate is safe and usable as a **content-production release**, without publishing anything.

## Exact scope

Repository: `thiendzung/ContentEngine`  
Branch: `release/content-production-v1-rc1`  
Issue: #417

Founder/MG will provide or re-confirm the exact candidate SHA before execution. Do not substitute another ref.

## Release boundary

The release must support:

```text
brief/evidence
→ Angle
→ Founder gate
→ Outline
→ Founder gate
→ EN + vi-VN Writer
→ Human Voice + quality
→ Founder final gate
→ deterministic review package
→ STOP
```

No direct WordPress write. No Git/Astro publish. No MOTGU OPS mutation. No production publication.

## RC1 batch

- G01 — Pillar — where to buy original art in Hanoi
- G02 — Pillar — how to bring a painting home from Vietnam
- Q05 — Cluster — original painting vs hand painted reproduction
- Q07 — Cluster — what does a certificate of authenticity prove
- Q06 — Cluster — artwork condition report before buying online

For verification, prove **one** bounded item can enter the canonical pipeline and reach the first human gate. Do not run all five merely to verify the release.

## Preconditions

1. Verify repository identity and exact assigned SHA.
2. Worktree must be clean; stop on unexpected changes.
3. Read:
   - `AGENTS.md`
   - `AI_context.MD`
   - `docs/PLAN.md`
   - `docs/TASKS.md`
   - `docs/releases/CONTENT_PRODUCTION_V1_RC1.md`
   - `docs/releases/content-production-v1-rc1.json`
4. Confirm authorized DB/environment. Never reset or migrate operational data merely for this proof.
5. No polling loops, `sleep`, `ps` or `pgrep`. Use existing one-shot/event/process-exit paths.

## Verification

### A. Static contract

- release doc and JSON manifest agree;
- active docs point to Issue #417 and manual WordPress publication boundary;
- batch is exactly G01/G02/Q05/Q07/Q06;
- no active instruction requires OPS/Git/Astro publication for RC1;
- package remains non-publishing;
- no stale active instruction says WordPress is forbidden for this RC1.

### B. Tests

Run the appropriate exact-SHA checks for the changed scope. Because RC1 changes release/docs rather than production algorithms, do not invent a broad code rewrite.

Minimum:
- repository documentation/format checks that apply;
- existing focused package/manual-handoff tests if present;
- existing operator intake/start-to-angle focused tests if they can run in the authorized disposable/test environment;
- **frontend lint, typecheck and production build** on the exact candidate SHA;
- **browser smoke** of the new beginner `/operator` home, advanced `/operator/journal/new`, and one existing `/operator/journal/{caseId}` case:
  - beginner sees three routes: planned content, production board, Needs Me;
  - planned content opens the existing Question Map, without bypassing Founder selection;
  - system preflight still blocks manual intake when not READY;
  - advanced brief preserves all required backend fields;
  - live state, approval and error/reconcile controls are unchanged;
  - case briefing details can expand/collapse;
  - mobile and keyboard navigation remain usable;
- full `make check` only if it is the normal exact-SHA gate and safe for the configured test DB.

Record commands and actual results. Never claim CI or local PASS that was not run.

### C. Runtime proof

In the authorized local/test/disposable environment:

1. run operational preflight;
2. confirm one-shot worker path;
3. create one bounded RC1 intake from the locked release brief;
4. use the existing canonical pipeline;
5. stop at `AWAITING_APPROVAL / human_gate=angle`;
6. verify no WordPress, Woo, Git, Astro, MOTGU production or publication side effect;
7. preserve exact Case/Run/Angle artifact IDs and hashes;
8. do not approve the Angle.

If evidence/provider configuration blocks the run, stop with the exact blocker. Do not change code or weaken evidence gates unless MG sends a separate bounded coding task.

## PASS criteria

Return `PASS_CONTENT_PRODUCTION_V1_RC1` only when:

- exact candidate SHA verified;
- static release contract is coherent;
- beginner/advanced UI smoke checks pass without changing backend authority;
- required safe checks pass;
- one RC1 item reaches the first human gate through the canonical path;
- no case-specific bypass/direct SQL;
- no publication side effect;
- no hidden dependency on OPS/Git/Astro for producing the review package.

Otherwise return `BLOCKED_CONTENT_PRODUCTION_V1_RC1` with the first exact blocker.

## Report format

```text
GOAL
EXACT_SHA
WORKTREE
STATIC_CONTRACT
CHECKS_RUN
CHECKS_NOT_RUN
RUNTIME_CASE
CASE_ID
RUN_ID
ANGLE_ARTIFACT_ID
ANGLE_HASH
STATE
PUBLICATION_SIDE_EFFECTS
BLOCKERS
STATUS
NEXT
```

Stop after the report. Do not merge.
