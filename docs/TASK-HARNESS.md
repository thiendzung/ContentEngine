# TASK HARNESS - one bounded engineering outcome

Use `docs/logs/YYYY-MM-DD-<task>-task.md`. This template is for development, local proof and deployment. Normal production uses the implemented operating grant and restricted loop from `21-AGENT-OPERATED-JOURNAL-SPEC.md`, not a fresh Founder-copied task for every stage.

A planned task is not execution permission. MG defines scope; Founder dispatches it to the separate Agent Local application. No direct MG-to-app delivery is assumed.

## Identity and outcome

TASK ID / OWNER / REVIEWER:
MODE: ENGINEERING_READ_ONLY / IMPLEMENTATION / LOCAL_ACCEPTANCE / DEPLOYMENT
OBJECTIVE (one observable result):
SPEC VERSION / DEPENDENCY EVIDENCE:
STATE: planned / dispatched / reported / verified

## Ref and safe synchronization

Repository / assigned branch / exact candidate SHA:
SPEC_REF and current task location:
Current deployed ref (do not change unless authorized):
Writable files (exact list or NONE):

Inspect status first. Preserve dirty files; no reset/stash/clean. Fetch metadata and verify the intended ref. Read checked-out AGENTS/context/spec/tasks/checklists. Record tested SHA/tree. Recheck a moved gate; never switch deployed code during an active step.

## Local target and inputs

Environment: TEST or OPERATIONAL (explicit permission required)
Redacted target identity / expected migration / resource ownership:
Retained evidence that must remain untouched:
Exact input/approval/artifact/settings references and expected hashes:
Canonical source of those refs:

A past Markdown log is not proof current rows/resources still exist. Never print connection strings, secrets or private content in the report.

## Permission and budget table

| Action | Allowed? | Boundary |
|---|---|---|
| Read operational DB | NO unless stated | Read-only transaction, named necessity |
| Write runtime/artifacts | NO unless stated | Exact cases/actions |
| Model/research calls | ZERO unless stated | Approved route/destinations; per-step AND total calls/attempts/time; known cost limits only |
| Code edit | NONE unless stated | Exact files, minimal patch |
| Install/login/service changes | NO unless stated | Exact service, recovery plan |
| Migration/release | NO unless stated | Exact source/target, backup/restore and safe checkpoint |
| Record a real content decision | NO by agent identity | Human-authenticated exact decision; test fixtures clearly synthetic |
| Git evidence branch/PR | NO unless stated | Sanitized paths, no main writes |
| Merge/publish | NO | Founder merge, separate publication decision |

Unknown permission/required budget = STOP. A model/auth error does not permit a different provider. Approval of this task does not create a general production grant.

## Commands and branches

Only documented/code-verified entrypoints. Proposed commands must be marked NOT IMPLEMENTED. For each branch state: condition -> permitted action -> evidence -> STOP. Include stale input, permission/config error, ambiguous external result, budget exhaustion, hard quality failure and success. Several harmless checks already within scope do not need repeated authorization.

## Acceptance and evidence

List acceptance IDs from `AGENT-OPERATED-ACCEPTANCE.md` plus applicable existing checklist tests. Supply expected terminal state, counters and zero-side-effect checks.

Evidence: start/end SHA/tree, safe environment identity, caller role/grant reference without credential, exact artifact/check/approval refs, commands/tests actually run, duration/counters, error layer/last completed step, checks not run and retained private evidence location.

Do not conflate implementation, CI, local acceptance, deployment, content approval or publication. Test-fake decisions are not real editorial approval. Docs-only work requires link/scope/consistency review, not invented runtime claims.

## STOP and report

STOP on unexpected work, changed target/input, forbidden/unsafe action, unresolved result, secret risk, exhausted budget, actual content gate or the bounded result. No next task on your own. Normal production continuation is a separately activated product behavior, not an exception an engineering agent may infer.

Return one packet:
`TASK / START-END REF / TARGET / FILES CHANGED / COMMANDS-CHECKS / EVIDENCE / ACCEPTANCE / NOT RUN / BLOCKERS / READY FOR REVIEW or BLOCKED or NEEDS CHANGES / NEXT FOR MG`

Founder relays it to MG. If evidence could not be posted on GitHub, state that explicitly; do not invent a link or claim synchronization.
