# CE05 — Production-first operating mode

Date: 2026-09-11
Owner: Founder + MG Content Engine
Status: **ACTIVE DECISION**

## Decision

CE05 now prioritizes getting one real MOTGU Journal into actual operation as soon as the current T05.15 quality gate is clean.

Do **not** keep adding speculative hardening before the first operational Journal. The remaining harness/debug/replay/review/metrics work must be driven primarily by observed failures and friction from real operation.

This does not waive any already-active content-quality gate and does not authorize automatic publishing.

## Non-negotiables that remain unchanged

- T05.15 must complete with the final VI and EN snapshots passing the bounded quality gates.
- Existing EvidenceSet, OriginalityPack, Assertion Audit and source-copy contracts remain authoritative.
- Final human content approval remains mandatory before the final `ContentVersion`.
- Artifact/version changes invalidate prior approval for that artifact version.
- No auto-publish, scheduler, autonomous prompt learning, new provider, new agent role or generic workflow framework is introduced on this path.
- WordPress automation remains later publishing/integration scope; the first operational Journal may use a controlled manual publish handoff.
- Founder remains the final merge and final content-approval authority.

## New critical path

```text
T05.15 final VI + EN PASS
→ T05.16 MINIMAL OPERATIONAL PACKAGE
→ Founder final content approval
→ approved ContentVersion / deterministic publish handoff
→ T05.17 ONE REAL OPERATIONAL JOURNAL
→ record real failures + operator friction + missing data
→ T05.18–T05.22 harden only what reality proves useful
```

The objective is not to declare the system complete before use. The objective is to get a safe, traceable, human-controlled V1 into use, then improve the harness from evidence.

## T05.16 — Minimal Operational Package

T05.16 is deliberately narrow. It should package the already-passing final locale artifacts for operational use without redesigning the engine.

Required outcome:

- exact final VI and EN draft IDs/versions/hashes are bound;
- exact final Assertion Audit and source-copy PASS evaluations are bound;
- existing `ContentItem` / `ContentVersion` contracts are reused where applicable;
- one deterministic final/publish package is created per locale or one explicitly bilingual package if the existing contract already supports it;
- package contains only the fields an operator needs to review and place the Journal into the real publishing surface;
- provenance/quality refs remain inspectable;
- exact rerun is idempotent;
- no provider/model/research call is needed merely to package final content;
- final human approval is explicit before the `ContentVersion` is treated as approved.

Prefer a simple manual handoff/export over building the future WordPress adapter early.

## T05.17 — One Real Operational Journal

T05.17 is no longer treated as a demonstration after all hardening. It is the point at which the V1 enters controlled real use.

The first operational run should:

1. use the exact approved T05.16 package;
2. move through the real human operating path used by MOTGU;
3. publish/place the Journal manually if the automated publishing adapter is not yet in scope;
4. keep the system-of-record IDs/hashes and final human decision traceable;
5. capture a short operational observation log.

Minimum observation log:

- what the operator had to do manually;
- where state or instructions were unclear;
- any retry/replay difficulty;
- formatting or content-package defects;
- missing data or provenance visibility;
- runtime errors or awkward recovery steps;
- total operator interventions that were actually necessary;
- what should be automated next versus what is acceptable to remain manual.

Do not build fixes before observing the corresponding problem unless the issue is a safety/data-integrity blocker.

## T05.18–T05.22 — Post-operation hardening

These tasks remain part of CE05 closeout, but they no longer block the **first** real operational Journal after T05.17.

### T05.18 Critical Gate Regression

Run the existing critical regressions and add regressions for failures actually observed during the operational Journal. Avoid broad speculative test expansion.

### T05.19 Resume / Replay Gate

Harden resume/replay around the interruption points that real operation exposes. Preserve immutable failed attempts and exact-input idempotency.

### T05.20 Human Review Surface

Improve the review surface only where the actual operator experience shows friction. Do not build a large dashboard pre-emptively.

### T05.21 CE05 Metrics Baseline

Start recording useful operational measurements from the first real run. Establish a baseline after a small real sample rather than inventing targets before operation.

Useful initial measures include:

- end-to-end run success/failure;
- number of human interventions;
- number and class of quality findings;
- retry/recovery events;
- manual steps that remain outside the engine;
- time or effort concentrated in specific stages;
- content changes requested by the final human reviewer.

### T05.22 CE05 Closeout

Close CE05 when the operational path is understood and the important observed failure modes have a bounded response. CE05 does not need to eliminate every future manual step.

## Operating rule after T05.17

```text
REAL RUN
→ OBSERVE
→ CLASSIFY
→ FIX THE SMALLEST REAL BOTTLENECK
→ ADD REGRESSION / HARNESS ONLY FOR THAT FAILURE MODE
→ RUN AGAIN
```

Use production evidence to choose the next engineering task. Do not let roadmap completion percentages or speculative architecture outrank actual operating feedback.

## Immediate effect

The current PR #51 and its post-merge T05.15 EN v5 revalidation remain the active gate.

After T05.15 final PASS, MG should issue one exact T05.16 task using the real final artifact IDs/hashes. That task must optimize for the shortest safe path to the first real operational Journal, not for completing T05.18–T05.22 first.
