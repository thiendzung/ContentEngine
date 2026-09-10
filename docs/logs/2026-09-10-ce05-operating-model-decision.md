# CE05 Operating Model Decision

Date: 2026-09-10

## Decision

ContentEngine uses one shared project brain: the GitHub repository.

Fixed roles:

- Founder = product/brand authority, strategic decisions, merge authority.
- MG Content Engine = primary architecture/engineering/project agent, PR/review/CI/state owner, delegates bounded local work.
- Agent Local = controlled local executor for exact delegated runtime/DB/credential/environment tasks; no scope expansion, no architecture redesign, no merge, no self-directed next task.

## State model

```text
GitHub live state → HEAD / branch / PR / CI
AGENTS.md        → operating constitution
AI_context.MD    → current semantic window only
docs/TASKS.md    → roadmap/progress
docs/CHECKLIST.md→ execution/review gates
docs/logs/*      → exact task instructions + historical evidence
```

Dynamic GitHub state is not duplicated in `AI_context.MD`.

## No stale semantic checkpoint

A task PR that changes phase/gate/next action must carry its own semantic state transition in `AI_context.MD` and `docs/TASKS.md`. The next task must not start while the shared semantic context still describes the prior task as active.

## WIP limit

At most:

```text
1 primary implementation task
+ 1 delegated local verification task
```

## Current speed policy

After this governance/state reset merges, meta-work stops. The critical path is:

```text
REAL O4 Angle
→ Founder selects exact Angle
→ Outline
→ VI + EN drafts
→ Review/Revise
→ Assertion Audit
→ source-copy check
→ Final Package
→ ONE REAL JOURNAL PASS
```

No new provider, agent, framework, generic abstraction, architecture redesign, automated publish or automated merge before the real Journal pass unless a hard blocker proves it necessary.

## Phase authority

For active repository work, phase numbering in `docs/TASKS.md` is authoritative over older external operating-map numbering.
