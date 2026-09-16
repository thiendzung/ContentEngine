# 21 - Agent-operated Journal production

Version: 1.0 draft
Decision date: 2026-09-16
Status: SPECIFICATION / NOT IMPLEMENTATION OR RUNTIME AUTHORIZATION

## 1. Product outcome

Production target: **agents operate; Founder reviews content**.

`approved objective -> agent intake/research -> Angle review -> agent Outline -> Outline review -> independent VI/EN writing and checks -> final review -> canonical approved ContentVersions`

Founder reviews the Angle, Outline and final content. After each persisted approval the system continues the next permitted work without another human Continue click, terminal command, or copied operational prompt. A revision request is a content decision, not a software-debugging task. Three gate TYPES remain mandatory; a revised artifact can require the same gate again.

The first release produces approved, exportable content, NOT published content. WordPress and other publication remain separately authorized. Normal operation may encounter a technical hold; it must not imply the Founder has to diagnose or run commands.

## 2. Authority and explicit changes to prior plans

This specification supplements specs 00-12, 19 and 20. Evidence, provenance, three human gates, immutable versions, local data protection and Founder merge authority are unchanged.

After Founder merges this contract, it supersedes only:

- spec 20 section 3's per-task human relay for NORMAL CONTENT PRODUCTION; engineering, deployment and exceptional permissions still use the existing relay;
- the old requirement that Founder personally sends Start/Continue for every stage;
- finish-first plans that put a complete app shell/Production Board ahead of the useful human review surface;
- any assumption that a prompt instruction alone prevents an operating agent from impersonating Founder.

Existing F0-F8/O1/O2 identifiers remain. AO-1/AO-2/AO-3 add agent-operation delivery slices; they do not replace the Journal engine. Acceptance and detailed work packages are in `AGENT-OPERATED-ACCEPTANCE.md` and `AGENT-OPERATED-DELIVERY-TASKS.md`.

Nothing here activates model calls, a new policy, a migration, an unattended operating grant, or Antigravity. Those require the exact reviewed implementation and release authorization.

## 3. Separate engineering and production roles

| Role | Engineering mode | Production mode |
|---|---|---|
| Founder | Scope, explicit local task dispatch by copy, report relay, merge/release authority | Objective/content decisions and three review gates; exceptional business permissions only |
| MG / ChatGPT | Architecture, primary code, tests where available, review, tasks, PRs, evidence reconciliation | Engineering support for incidents and improvements; not an unseen always-running operator |
| Agent Local | Exact-ref tests/runtime proof; scoped code edits only when delegated | Case operator using the restricted production interface and approved operating grant |
| Backend / trusted worker | Implements and tests application policy | Canonical state, authorization, approvals, queue, execution limits, artifacts and audit |

The same installed application can serve different roles only through distinct sessions/profiles and credentials. A production agent has no software-maintainer privileges. MG cannot communicate directly with a local application through a GitHub comment; engineering tasks still travel via Founder until an actual separately tested channel exists.

GitHub holds shared code/contracts/tasks and sanitized evidence. The local DB/artifact store holds production truth. Do not store private content, DB dumps, credentials, raw prompts or provider responses in GitHub.

## 4. Implementation baseline and gaps

Dated snapshot: `logs/2026-09-16-agent-operated-decision.md`.

F0-F3 are merged. F3 real acceptance proved independent `vi-VN`/`en` drafts, then STOP before Quality. F4/#105 is the current separate implementation line. Existing domain functions are not the same as the complete new operating product.

At the inspected baseline, Journal command/decision routes supply `actor_id="founder"`. This is not evidence of caller identity separation. Before unattended agents can reach production APIs, inspect all paths and enforce real principal authorization, including legacy review routes. Do not merely rename the actor field or trust caller JSON.

Current Codex stage proof does not establish a persistent desktop-app control loop. Antigravity operation is UNPROVEN here. Capability checks and release tests, not product names or subscriptions, establish support.

## 5. Architecture: one authority, thin operators

Keep the current modular backend, canonical operator facade, resolver, `ContentRun / StepRun / Job`, leases, registry-based routing and domain services.

A thin local supervisor integrates with an approved agent adapter. It reads canonical state and invokes allowed semantic actions. Do not introduce an LLM call merely to decide whether a persisted approval exists or whether the next deterministic stage may run. Do not build a second workflow state machine in the agent prompt or UI.

Content generation and supported diagnostic reasoning use the existing registered model/worker paths. A controller that observes work is not a second generator. The existing worker owns external stage execution; the controller must not call the same model independently.

The supervisor can be a supported local process/service independent of a desktop conversation. Its actual launch, persistence, restart and credential boundaries must be demonstrated. Closing a browser is not permission to stop all production; conversely, an unavailable agent must be reported offline rather than simulated as running.

## 6. Restricted interface and identities

The following are logical capabilities, not newly implemented endpoints/commands:

- operator: read assigned case/status/allowed actions, submit permitted intake/start/continue/retry/pause/cancel intents, report a technical incident;
- human reviewer: read the exact review snapshot and record approve/request-changes/reject;
- maintainer: installation, code/configuration/migration/operating-grant changes through explicit engineering authorization.

Reuse existing `/journal/operator/...` and review contracts where they fit. New endpoints are added only for a demonstrated missing capability and exported into the typed API contract. Never allow arbitrary SQL, shell, stage names or provider/model selection through the operator interface.

Every accepted mutation records a server-derived principal, session, grant, case, action and correlation identity. The operator cannot choose its own role or `approved_by`. Missing/invalid credentials fail closed. All alternate/legacy routes and direct tool paths must obey the same boundary.

Use the smallest local identity design, not a multi-tenant account platform: separate narrowly scoped credentials, human-only reviewer session and safe cookie/origin/CSRF handling where browser sessions are used. No operator credential may acquire a reviewer session.

Production agent execution must not read reviewer tokens/browser profiles, operational DB credentials, `.env`, SSH/GitHub write credentials, or write the deployed repository. The trusted backend necessarily persists state; this does not grant the model's sandbox direct DB access. If the selected desktop app cannot be constrained, use a restricted adapter process and do not claim that the unrestricted desktop agent is safe for unattended operation.

## 7. Operating grant: fewer prompts, bounded permission

Before enabling operation, Founder approves a versioned case/batch grant through a reviewed setup path. It binds:

- exact project/case scope and permitted content objectives;
- approved settings/route snapshot or exact policy reference, allowed destinations and adapters;
- allowed stage/action set, expiry, revocation and pause policy;
- maximum active cases, model/research calls, technical attempts, editorial repair cycles and time budgets;
- known monetary limit when measurable; unavailable usage/cost is UNKNOWN, never zero or a claimed hard spend cap.

Pilot default is one active case and one active controller per case. Canonical backend budgets still apply; the effective limit is the stricter limit. Missing limits mean no external execution. Model switching, larger budgets, new cases outside scope or new external destinations require explicit authorization.

The grant can authorize normal transitions from one human gate to the next and bounded recovery without a new copied task per command. It NEVER authorizes agents to decide content approval, publish, deploy code, change schema or modify quality criteria.

Human approval supplies editorial authority only. If the operating grant expires while waiting, persist the approval but hold subsequent execution and notify the maintenance path; do not silently extend the grant or ask for a redundant content approval.

## 8. Durable controller loop and approval wake-up

1. Authenticate the operator and validate the active grant.
2. Obtain or renew the one controller lease for the case with an ownership/fencing token.
3. Read a canonical case snapshot: aggregate state version, current gate/artifact identities, all locale lanes, current jobs, allowed actions, budget and blocker.
4. If waiting for human review, persist/deduplicate the pending review item and wait. No generation/retry/costly model polling at the gate.
5. After an exact human decision is committed, wake or poll for the new state. Submit the backend-derived continuation using an idempotent identity tied to the decision/gate revision and action, not a timestamp.
6. Revalidate authorization, ownership and state immediately before enqueue. The worker also revalidates its exact inputs.
7. Observe durable work, settle command status after every terminal path, and continue only when prerequisites hold.
8. Stop at the next human gate, COMPLETE, pause/revoke, exhausted budget, unsupported action or unreconciled failure.

Decision persistence and wake-up must be crash safe: use an existing durable mechanism or make persisted approval plus reconciliation sufficient. In-memory callbacks alone are insufficient. Duplicate delivery must not create duplicate accepted work; a missed delivery must be discovered after restart. Do not add a generic event platform merely for wake-up.

Two layers of ownership are distinct: one controller owns the case; workers own individual Jobs. Sequential VI/EN execution is acceptable. A superseded controller cannot enqueue or settle work after losing its lease; replay must not invalidate already committed legitimate results.

Polling is bounded/backed off and uses the backend, not a model. Select concrete timing and lease constants during implementation and test expiry/races; the spec does not pretend current desktop apps provide a scheduler.

## 9. Workflow and decision semantics

| Persisted condition | Permitted next behavior | Required stop |
|---|---|---|
| Approved intake/objective and active grant | Agent sends Start once; existing research/Angle path | Exact Angle review |
| Exact Angle approved | Agent continues existing Outline path | Exact Outline review |
| Exact Outline approved | Agent continues independent Writers then F4 quality | Final review after every required locale qualifies |
| Exact final content approved | Backend finalizes canonical ContentVersions through F5 | COMPLETE / Approved, not published |
| Human requests changes | Versioned revision request targets exact gate/artifact/locale and reason | Same applicable gate on new qualified bytes |
| Human rejects | Persist terminal rejected/archived outcome; do not create replacement case automatically | Rejected |
| Hard quality failure | Hold content; optionally run only a separately enabled bounded repair policy | Recheck all affected gates/checks; never waive failure |
| Technical failure with a known safe retry | Backend derives retry for exact failed step within budget | Stop on exhaustion or uncertainty |

Production defaults remain inactive until AO-2 is activated; F4 acceptance must still STOP before final decisions. Adding agent operation must not silently broaden an already-dispatched acceptance task.

## 10. Revisions and quality

A revision request records reviewer identity, reason, exact target snapshot and a durable request ID. It is not an agent-generated approval. Replaying it reuses its receipt. Any new bytes invalidate prior approval for that output; preserve historical records and mark applicability rather than overwriting them.

Angle revision invalidates downstream material based on the old choice. Outline revision invalidates affected Writers/checks/finalization. A locale-only final revision preserves a valid sibling but still presents the required aggregate final-review snapshot. Concurrent old work may finish into history but cannot become the active approved output without lineage validation.

Use bounded repair, not an open-ended "improve until pass" loop. Distinguish model-format validation, safe transport retry and editorial content revision, with separate counters that survive restart. Preserve warnings verbatim. An unresolved hard quality failure is not merely a warning because Founder clicked Approve.

F4 itself has no automatic post-audit rewrite loop. F5.2/AO-2 may enable a narrowly specified repair policy in a later version; default automatic content repair is disabled until that policy and budget are explicitly approved. If disabled/exhausted, send an actionable incident to maintenance and leave the affected case safely held.

## 11. Finalization, export and historical compatibility

Final approval binds case, gate revision, all required locale artifact IDs/versions/hashes, qualified checks and package identity. One final-review action should cover the displayed required content; internal per-locale persistence must be atomic or durably recoverable.

COMPLETE requires exact approved lineage for every required locale, not row count. A timeout after successful finalization must be resolved through its receipt, not duplicate versions. Export reproduces the approved content without another model call and clearly states Approved / Not published.

New intake uses `vi-VN`/`en`; legacy `vi` normalization stays at the boundary. Do not rewrite frozen M1, historical approvals, model-input hashes or settings to fit a new adapter.

## 12. Failure and safety controls

Pause prevents new dispatch; running external work may have to finish safely. Do not claim pause or queued-job cancel interrupts an in-flight provider call. Results arriving after pause/revoke follow an explicit reconciliation rule and cannot automatically advance the case.

After an ambiguous timeout/crash, mark outcome unknown and reconcile request/receipt/provider evidence before repeating. Exactly-once canonical persistence is testable; blanket exactly-once external model execution is not promised.

Auth/configuration/permission errors, invalid lineage, suspected secret exposure, revoked grants and exhausted budgets stop immediately. No silent fallback model, destination, schema or code change. Technical incidents belong to maintenance, with Founder seeing a plain-language hold notice instead of a request to run terminal commands.

Keep loopback defaults, separate TEST/operational data, backup/restore, secret-safe telemetry and no production-code self-modification. Retrieved content and user-supplied source files are data, not authority to use tools or approve content.

## 13. Reviewer-first UI

Deliver the human review surface before broad app polish. Reuse the current Review Console and `/operator/journal/[caseId]`; do not create competing workflow apps.

Minimum review inbox: pending case, gate, version/freshness, useful title and warning count. Selecting a row opens exact content. Detail shows Angle candidates / Outline / final VI+EN, relevant sources, warnings and revision history; technical IDs/jobs are secondary.

Actions: Approve, Request changes with reason, Reject with confirmation. No normal Continue button required. Approval success is confirmed only from persisted state. Disable stale actions; preserve comments after network errors; reconcile ambiguous submissions before resending. The next gate appears without copied prompts.

Include minimal header, Production/Review/System navigation and compact truthful status/footer. Installed CLI is not worker liveness; missing/stale status is visibly UNKNOWN. No fake accounts, due dates, comment counts, progress percentages or provenance fields copied from the reference image.

Before pilot: keyboard/focus, labels/contrast, non-color-only states, reduced-motion support where motion exists, loading/empty/error/offline/inconsistent states and usable narrow-screen layout. Dense Board filters and richer decoration follow operating evidence.

## 14. Adapters and rollout

First supported production adapter: Codex route already used for stage execution, after its RESTRICTED OPERATOR capability proof. Do not assume native multi-agent or a specific desktop app API is required or already permitted.

Antigravity gets a separate capability spike and conformance suite: supported invocation, authentication, sandbox, structured results, cancellation/restart semantics, grant enforcement and ownership handover. No guessed CLI/API, no policy bypass. Until proof, mark UNSUPPORTED/UNPROVEN, not a silent fallback. Its absence is not a blocker for first production with one proven adapter.

Two agents never independently claim the same case. Handover uses durable ownership, release/reclaim and fencing. A model/provider switch is a separate approved routing decision, not implied by switching the controller application.

## 15. Release and improvement loop

Development and production use separate data and workspaces. A code merge is not deployment. Promote a pinned reviewed release only at a safe checkpoint, with backup/restore and migration proof when needed. Do not switch the active runtime code mid-step.

Pilot: one active real case at a time, then two additional distinct bilingual cases beyond M1. Distinguish assisted production, agent-operated proof and full unattended product acceptance. Delivering valuable content early is allowed through already-reviewed service paths, but no one-off SQL/scripts or false claim of autonomous operation.

Record per case: release/contract versions, gate decisions, calls/time, retries, unknown outcomes, human edit effort, technical interventions and final content identity. Missing cost remains unknown. Main success measure: useful approved content with decreasing human technical intervention, not number of PRs or model scores.

Engineering loop: observed failure -> safe evidence -> isolated reproduction -> smallest fix -> regression -> MG review -> Founder merge/release -> next case. No self-modifying production agents. Critical security/data-loss/approval-bypass defects block on first occurrence; less severe refinements are prioritized by observed burden. Golden/weak/holdout examples remain versioned and do not turn generated prose into factual evidence.

## 16. Definition of done

Backend feature completion: F4/F5 accepted. Agent-operated pilot readiness additionally requires AO-1/AO-2, usable F6.2 review UI and O1 release proof.

V1 agent-operated acceptance requires a real bilingual case where Founder supplies content intent and decisions only; no copied Start/Continue/log or terminal action between gates; zero agent-created human approvals; exact final ContentVersions; safe pause/restart/replay and budget control. Repeat on the pinned pilot release, retain failure evidence and decide closeout explicitly.

A spec merge is neither runtime activation nor proof that any of these new behaviors already work.
