# Agent-operated product decision and baseline

Date: 2026-09-16
Author: MG / ChatGPT
Scope: requested specification, detailed tasks/checklists and repository planning update
Status: PROPOSED CONTRACT IN DOCS PR; NO NEW LOCAL EXECUTION EVIDENCE

## Founder direction captured

Founder clarified that local agents such as Codex/Antigravity are intended to operate content production permanently, while Founder reviews content. Founder requested a specification and detailed task/checklist pack for MG and Agent Local to complete the software on that basis.

The engineering collaboration remains MG architecture/code/review/planning, Agent Local scoped local proof, and Founder copy/relay/merge. Normal future content production must not depend on copied per-stage operational prompts. This is a substantive operating-contract change, not simply another status-sync PR.

## Live GitHub observations at preparation

- [main ref](https://api.github.com/repos/thiendzung/ContentEngine/git/ref/heads/main): `5eef4e72cb15bc6ea30488a15f18a5de091053d6`.
- [F3 PR #104](https://github.com/thiendzung/ContentEngine/pull/104): MERGED, reviewed head `c49953c36729c2a9d8ff27cda50d3c368425f703`, merge `5eef4e72cb15bc6ea30488a15f18a5de091053d6`. PR receipt records CI #1035 and F3.A2 real acceptance PASS through independent canonical drafts, then STOP before Quality. Older F3-planning-only context was stale.
- [F4 PR #105](https://github.com/thiendzung/ContentEngine/pull/105): inspected Draft, initial head `ba9c3ed913cd1a24dce380035c16d0fe6cd472d1`, separate implementation contract for Quality -> final human gate. This docs change does not move that branch or expand its acceptance.
- Inspected `backend/app/modules/content_engine/journal/router.py` at main includes `actor_id="founder"` in command/decision calls. This motivates full AO-1 identity-path review; it does not prove that global middleware already supplies or lacks every needed control.
- Read governing AGENTS, context, PLAN, TASK-HARNESS, CHECKLIST, current task index, F4 contract and the existing route surface.

No fresh local checkout/DB/service/capability inspection was performed. Prior recorded operational schema `0027` and code/test `0034` are not a new operational query. F3 acceptance does not establish a restricted always-running desktop controller or Antigravity capability.

## Documents introduced

- `../21-AGENT-OPERATED-JOURNAL-SPEC.md`: operating model, identities/grants, continuation, revisions, recovery, reviewer UI and rollout.
- `../AGENT-OPERATED-DELIVERY-TASKS.md`: bounded packages, owners, dependencies, checklists, tests and STOP conditions.
- `../AGENT-OPERATED-ACCEPTANCE.md`: traceable negative/positive acceptance matrix and release blockers.
- `2026-09-16-ao-d0-local-baseline-task.md`: first copy-dispatched read-only local/capability report.

Current entrypoints/context/tasks/checklists and old roadmap pointers are aligned. Spec 21 explicitly narrows which older normal-production dispatch/UI assumptions it supersedes; existing hard gates and local-data safeguards remain.

## Key choices

One proven restricted adapter is enough for first production. Antigravity has its own later conformance task rather than blocking the useful path. Keep one controller per case and per-Job worker ownership. Use the existing deterministic resolver/worker; no LLM polling or second workflow engine. Enforce human-only approval in credentials/API/sandbox. Keep engineering self-repair separate from production.

First-use acceptance is a useful review UI plus safe agent-operated production, not a completely decorated dashboard. Revisions and hard quality failures remain bounded and honest. Publishing, route/model activation, migrations and production grants are separate permissions.

## Review and remaining checks

Performed: live repository/PR/contract reads and manual specification/task/acceptance consistency review. No new code, schema, model call, research, content approval or production mutation is part of this change.

Local sandbox could not download repository text through its network, so no full checkout/build/test is claimed here; GitHub connector reads/writes are the source for this docs change. Required docs/CI checks must be recorded against the final PR head, and Agent Local agreement remains pending its returned AO-D0 report.

Founder still dispatches AO-D0 by copying the exact-ref prompt. A GitHub document/comment is not evidence that the separate local agent received it.
