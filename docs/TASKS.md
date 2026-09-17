# TASKS - agent-operated ContentEngine delivery

Updated: 2026-09-17 on documentation PR #106; not a runtime grant.
Specification: `21-AGENT-OPERATED-JOURNAL-SPEC.md`.
Latest schedule/checklists: `logs/2026-09-17-fast-track-delivery-plan.md`.
Detailed implementation contracts: `AGENT-OPERATED-DELIVERY-TASKS.md`.
Acceptance matrix: `AGENT-OPERATED-ACCEPTANCE.md`.
Working window: `../AI_context.MD`.

## Completed baseline

| Item | State | Evidence scope |
|---|---|---|
| F0 / #93 | MERGED / browser acceptance | Exact Angle gate, not the full later UI |
| Planning / #101 | MERGED | Original finish-first delivery and relay roles |
| F1 / #102 | MERGED | Canonical operator facade/resolver |
| F2 / #103 | MERGED / real acceptance | Durable Outline and exact approval |
| F3 / #104 | MERGED / real acceptance | Independent vi-VN/en Writer drafts; no F4 completion |
| AO-D0 | RECEIVED / REVIEWED with qualifications | Read-only baseline, not security/service/adapter proof |

## Active and queued work

| ID | Owner | State / next action | Exit |
|---|---|---|---|
| F4 / #105 | MG primary code/review; Local proof | Candidate 42980c6..., CI #1057 success last checked; real success still pending | Both qualified final artifacts at final_review, no final approval/version/publish |
| F4-A5R-B0.3 | Agent Local; MG review | READY FOR FOUNDER RELAY; Outline decision recorded, local persistence not evidenced | Two Writer drafts, complete report + private pre-quality snapshot, STOP |
| F4-A5R quality | Agent Local; MG review | WAITING Writer evidence and separate bounded authorization | Review v3/Audit/Source-copy -> exact final_review |
| F5.1 | MG; Local proof | NEXT IMPLEMENTATION AFTER F4 | Exact final decisions -> canonical versions / COMPLETE |
| AO-1 | MG; Local restricted-profile proof | After F5.1; design uses completed AO-D0 | Enforced reviewer/operator boundary and durable grant |
| F5.2 | MG; Founder decisions / Local proof | After F5.1 + AO-1 | Versioned revisions/rejection without full restart |
| AO-2 | MG; Local service proof | After AO-1 + F5.2 | Approval automatically resumes permitted work |
| F6.2 + minimum F6.1 | MG; Local browser / Founder usability | Read-model design with backend; integrate after AO | Full reviewer flow with usable header/menu/body/footer |
| O1 | Local maintenance; MG review / Founder release | Explicit release task after above | Pinned safe runtime, backup/restore, guarded deployment |
| F7 | Restricted operator; Founder / MG review | After O1 + explicit grants | Two distinct useful bilingual cases beyond M1 |
| Remaining F6.1/F6.3 + F8 | MG; Local proof / Founder | After useful production | Evidence-led Board/UX/content efficiency improvements |
| AO-3 / O2 | MG; Local proof / Founder | OPTIONAL | Antigravity conformance / routing only if needed |

Immediate packet: `logs/2026-09-17-f4-a5r-b0-3-writer-task.md`. Documentation SHA and executable SHA are distinct; do not checkout #106 as F4 runtime. F4 remains the single active implementation. While Local verifies a frozen candidate, MG prepares next-package contracts/tests without changing it.

## Common completion checklist

- [ ] One outcome, owner, dependency, exact code SHA and writable scope are explicit.
- [ ] Relevant automated tests pass; exact candidate/integration CI is reviewed, not inferred from another SHA.
- [ ] Local evidence proves applicable runtime/identity/browser behavior; unrun checks stay unrun.
- [ ] Report contains complete snapshots, content/findings, actual calls, receipts and side effects; one packet per meaningful gate.
- [ ] No unapproved model/research/deployment/publication actions; actual invocation budget includes failures and uncertainty.
- [ ] Context/task status and dated sanitized evidence agree; code, CI, runtime and deployment are not conflated.
- [ ] MG gives disposition; Founder alone merges/releases. Passing exits ends the package rather than opening polish.

## Release blockers

- [ ] F4/F5 exact output/check/approval/version path accepted, including revisions/rejection.
- [ ] Restricted operator cannot approve or access reviewer secrets/deployed code/direct DB/privileged bypass paths.
- [ ] Grants, limits, expiry/revocation, duplicate/missed wake-ups and controller takeover tested.
- [ ] Reviewer UI handles all three gates, refresh/stale/offline/double-submit, feedback preservation and basic accessibility.
- [ ] O1 proves actual schema/runtime identity and private backup/restore before real operation.
- [ ] Pilot records useful output and interventions honestly; critical defects stop the affected scope immediately.

## Retention and historical follow-through

Retain CE00-CE04, M1, Review Console/Board, observability/delegation, OPS-01/02, K1-K6, routing foundations and every hard-blocked case. AO-D0's reported old services/dirty files are not permission for cleanup. Its denial/runtime requirements remain attached to AO-1/AO-2/O1; see `logs/2026-09-16-ao-d0-baseline-review.md`.

Use explicit TEST_DATABASE_URL, distinct comparison DATABASE_URL, and global eligible queue isolation. Do not copy .env or query operational data under a test grant. A privately retained pre-quality snapshot can avoid upstream regeneration only through an authorized new isolated restore and exact lineage proof; never erase failed history or reuse approvals for changed artifacts.

Deferred: new workflow engine/provider/agent framework, Redis/Celery/Kubernetes, vector DB, broad multi-agent, complex Board/animation, Artwork/WordPress/publish automation. Security, recovery, revision correctness and useful review UI are not deferred polish.
