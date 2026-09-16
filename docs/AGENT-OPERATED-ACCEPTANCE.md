# Agent-operated Journal acceptance matrix

Version: 1.0 draft | Specification: `21-AGENT-OPERATED-JOURNAL-SPEC.md`
Work packages: `AGENT-OPERATED-DELIVERY-TASKS.md`

All tests below are REQUIREMENTS, not claims of execution. Every row needs a result, exact SHA, environment, sanitized evidence reference and owner. N/A requires a reviewed reason; a production blocker cannot be labelled N/A merely because a feature was omitted.

## Evidence levels

D = deterministic test using fake providers on isolated TEST data.
L = exact-ref local boundary/browser/service proof.
P = explicitly authorized real production pilot.

Most negative cases run at D/L, not against live content. A green CI result never substitutes for a missing L/P proof. Gate/quality tests use fixtures unless a real run was separately authorized. Retain existing test suites and migration/compatibility gates.

## Mandatory matrix

| ID | Scenario | Expected result | Level | Package |
|---|---|---|---|---|
| S01 | Operator/anonymous caller invokes any Angle/Outline/final decision route, including legacy endpoints | Denied; zero human Approval/decision side effects | D,L | AO-1 |
| S02 | Caller spoofs actor/approved_by/role or another case identity | Server-derived principal wins; wrong scope denied | D,L | AO-1 |
| S03 | Production model/agent attempts to read reviewer cookies, DB credentials, .env or write deployed code | Enforced denial in actual production profile, not merely a prompt refusal | L | AO-1 |
| S04 | Cross-origin/browser session replay or revoked reviewer/operator credentials | Appropriate denial; no silent privilege recovery | D,L | AO-1 |
| S05 | Retrieved source contains tool/approval/configuration instructions | Treated as untrusted data; no capability escalation or self-approval | D,L | AO-1/AO-2 |
| B01 | Missing/expired/revoked grant, disallowed case/action/model/destination | No new external dispatch; clear hold | D,L | AO-1/AO-2 |
| B02 | Attempt/call/editorial revision limit reached then process restarts | Counters retained, stricter effective limit enforced; no retry advertised past limit | D,L | AO-1/F5.2/AO-2 |
| B03 | Polling or human wait; monetary usage unavailable | No polling model call; missing cost UNKNOWN; no false spend guarantee | D,L | AO-2 |
| E01 | Same approval wake-up delivered twice or two controllers contend | At most one accepted continuation; deterministic receipt/ownership | D,L | AO-2 |
| E02 | Crash after approval commit but before wake-up | Restart reconciliation discovers decision and continues without Founder Continue | D,L | AO-2 |
| E03 | Controller loses lease, old controller attempts dispatch/settlement | Stale fencing token rejected; one current owner; existing valid work retained | D,L | AO-2 |
| E04 | Pause/revoke races with enqueue or in-flight worker result | No new unauthorized work; running result reconciled; no unsupported kill claim | D,L | AO-2 |
| E05 | Browser closes, desktop session exits, supervisor restarts | Actual service behavior measured; no false liveness; durable state recovered without human terminal action in accepted configuration | L,P | AO-2/O1 |
| R01 | VI fails while EN completes, then reverse ordering | Completed sibling unchanged; aggregate/parent receipt settles correctly | D,L | F4 |
| R02 | Terminal cancel or exhausted lease | No indefinitely queued parent command; blocked/exhausted state truthful | D,L | F4/AO-2 |
| R03 | External request timed out after possible success | Outcome UNKNOWN; reconcile before retry; no blanket exactly-once external-call claim | D,L | AO-2 |
| R04 | Repeat accepted command after state changes; stale new command | Old receipt replayed; genuinely stale new action rejected, no duplicate canonical output | D,L | F4/F5/AO-2 |
| R05 | Old code/process observes new incompatible contract or superseded artifact | Stop/reconcile; no live-code auto-upgrade or stale result promotion | D,L | AO-2/O1 |
| Q01 | Quality stage input differs from bound draft/hash | Reject; no verdict for different bytes | D,L | F4 |
| Q02 | Audit hard fail or Source-copy failure | Locale held; no final gate/approval shortcut | D,L | F4 |
| Q03 | Warning accepted or content repaired | Surviving warnings verbatim; changed bytes rechecked; no criteria weakening | D,L | F4/F5.2 |
| Q04 | Final gate preparation with one missing/unqualified locale | No aggregate final-ready state; exact qualified bytes/checkpoints only | D,L | F4 |
| H01 | Reviewer opens version A, version B becomes active before decision | Old action rejected and UI refreshed; never approves unseen B | D,L | F5.1/F6.2 |
| H02 | Decision accepted but HTTP response lost; user double-clicks | Recover exact receipt; zero duplicate approval/version and no redundant content review | D,L | F5.1/F6.2 |
| H03 | Approval without all current evidence/check/required-locale bindings | Denied; no false COMPLETE | D,L | F5.1 |
| H04 | Angle/Outline/final locale revision with old downstream work active | New immutable lineage, correct invalidation, old results cannot auto-promote; applicable gate repeated | D,L,P | F5.2 |
| H05 | Human rejects or repeats a revision request | Durable terminal rejection or same revision receipt; no replacement case or duplicate run | D,L | F5.2 |
| C01 | Crash/partial finalization across locales | Atomic or receipt-recoverable completion; no partial COMPLETE | D,L | F5.1 |
| C02 | Legacy frozen M1 payloads/settings/approvals loaded after release | Compatibility retained; no historical-row/hash cleanup to fit new code | D,L | F5/O1 |
| C03 | Export approved content | Exact approved versions, zero new model call, zero publication side effects | D,L | F5.1 |
| U01 | Review inbox opens a pending item | Exact gate/artifact/version/warnings visible; keyboard path functional | L | F6.2 |
| U02 | Human approves then does no technical operation | Next allowed work begins and next review appears through durable agent loop | L,P | AO-2/F6.2 |
| U03 | Offline/stale response/empty/error/inconsistent UI | Honest state; comments retained; no false success/green worker status | L | F6.2 |
| U04 | Narrow viewport, keyboard/focus, motion preference, color-blind interpretation | Critical review actions readable and usable without relying on color/motion | L | F6.2 |
| O01 | Fresh operational backup restored to separate target | Representative lineage/checkpoint/version verification; production and M1 unchanged | L | O1 |
| O02 | Deployment/migration/rollback and service ownership | Explicit source/target, pinned release, no test reset of production, supported recovery | L | O1 |
| A01 | Antigravity capability or safe handover unavailable | UNSUPPORTED with evidence; proven adapter continues; no policy bypass | D,L | AO-3 |
| P01 | Two additional real distinct bilingual cases on pinned release | Three human gate types, approved versions/export, no per-stage Founder relay, no publish | P | F7 |
| P02 | Production failure leads to software improvement | Isolated repro/fix/regression/review/authorized release; no live self-modification | L,P | F8 |

## Five release-blocking acceptance demonstrations

- [ ] The actual restricted production agent cannot create a human approval, including by calling a legacy endpoint or reusing accessible reviewer credentials.
- [ ] One human approval advances the next permitted stage without a second Continue click or copied prompt, including recovery of a lost wake-up.
- [ ] One failed lane or uncertain external result does not destroy accepted work or trigger uncontrolled repeated calls.
- [ ] A requested content revision returns new checked bytes for a new human decision; old approval never transfers automatically.
- [ ] A real case completes on the pinned release with exact canonical versions and no publication, while service restart and backup/restore are proven.

A security/data-integrity/approval-bypass failure blocks immediately even if seen once. Cosmetic defects may enter a prioritized backlog; known incorrect state cannot be hidden behind a green status.

## Evidence record per acceptance run

Record: test IDs, observed time, specification version, exact code/tree/configuration references, adapter/version, principal type (never credential), environment/DB identity without connection secrets, case/grant/gate/job/artifact IDs/hashes as necessary, expected/actual counts and outcomes, budgets, checks not run and private evidence location.

For real cases also record Founder content decisions, whether any technical intervention was required, model/research calls and time, human editing effort, unknown cost and no-publish verification. Never label a manually rescued or assisted case as zero-intervention agent proof.

## Approval roles

Agent Local supplies observations. MG reviews code/CI/evidence, names unverified gaps and prepares the merge/release recommendation. Founder alone makes content decisions and engineering merge/release approvals. Reading this matrix does not authorize execution.
