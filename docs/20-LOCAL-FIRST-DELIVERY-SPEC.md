# 20 - Local-first, finish-first delivery contract

Decision date: 2026-09-12. Effective after Founder merges this contract.

This document defines delivery order and local operating boundaries. It supplements specs 00-12 and `19-CE05-JOURNAL-ENGINE-SPEC.md`; it does not relax their data, evidence, approval or security contracts. Milestones M1-M4 are delivery outcomes, not replacement CE phase numbers. Features below are requirements, not claims of implementation.

## 1. Outcome and scope

Finish one useful real Journal, prove repeatability on the Founder's computer, then improve from observed failures and reader results. Do not build a more general platform first.

Keep FastAPI, Next.js, PostgreSQL, the existing modules, settings registry and CE03 harness. No required cloud deployment, new provider, new agent role, generic workflow builder, vector database, automated publishing or automated merge.

Local-first means the application, operational database and private artifacts run on the Founder's machine. Research/model services still need internet and valid authorized access. Offline generation is NOT promised. During a network outage retain committed checkpoints; resume only after checking state and any ambiguous external result.

## 2. One shared brain, distinct sources of truth

| Subject | Authority |
|---|---|
| Product contracts, architecture, code, approved tasks | Merged GitHub repository |
| Live commit, PR and CI state | GitHub live API/ref state |
| Current working window and next bounded task | `AI_context.MD` |
| Milestone order and task progress | `docs/PLAN.md`, `docs/TASKS.md` |
| Actual runs, approvals, evidence and artifacts | Verified local operational DB/artifact store |
| Runtime claims shared with MG | Timestamped, sanitized evidence in `docs/logs/` |
| Merge and final editorial decisions | Founder |

GitHub is not a substitute for the runtime DB or a backup of it. A Markdown checkpoint is an observation, not proof that rows still exist. `AI_context.MD` is the single exact filename; do not create a second `AI_context.md` differing only in case. It points to evidence instead of copying every UUID, PR number and historical result.

No credentials, cookies, sessions, `.env`, DB dumps, raw private/customer data or unreviewed CLI output may be committed. Treat the repository as public. Keep private artifacts local and share only necessary sanitized summaries/IDs/hashes.

## 3. Roles and fewer handoffs

Founder chooses business priorities, makes editorial decisions, approves/merges PRs and dispatches exact tasks by copying their instructions to Agent Local.

MG owns architecture, scoped implementation, tests it can actually execute, PR preparation, adversarial code review, review of local evidence and shared-state updates. MG must disclose self-review and checks not run. A GitHub connection does not give MG control of the Founder's machine.

Agent Local is the execution arm for local services, authenticated CLI, DB verification, real runs and local tests. It may implement only an explicitly delegated small patch with an exact file allowlist. It does not redesign, select the next task, invent an editorial approval or merge. It may record a verifiable, explicitly authorized human decision through the canonical approval path; it is not the editorial decision-maker.

Delegate one bounded outcome, not one approval request per shell command. A task can cover several already-authorized steps and stop at a real editorial gate or conclusive blocker. Maximum WIP: one implementation task plus one related local verification; only one writer/executor against the active runtime lineage.

Approval of a plan or merge of code is not approval to incur model charges, change an operational DB, approve content or publish. Exact tasks state permission and budget. Previously authorized editorial selection is usable only when the exact recorded rule, actor and artifact conditions can be verified; never manufacture an approval.

## 4. M1 - one real Journal, unchanged hard gates

Resume the fresh lineage in `docs/logs/2026-09-12-ce05-m1-one-real-journal-pass-status.md`. First verify current EvidenceSet/OriginalityPack bindings once. Do not redo research, recreate historical rows or start another case merely because Angle execution is blocked.

Path:

`verified inputs -> Angle -> Angle approval -> Outline -> Outline approval -> independent VI/EN -> bounded Review/Revise -> Assertion Audit -> Source-copy -> Operational Package V0 -> Founder final approval`

Keep all three editorial gates from spec 19. Both locales must have complete visible content. At the current accepted versions, Assertion Audit v5 must return non-fail with zero critical unsupported and contradicted assertions; Source-copy v2 must have zero failures. Preserve all non-critical warnings verbatim for Founder review. Missing provenance, unsafe execution, invalid/stale binding, fabricated facts and source-integrity failures remain blockers.

Operational Package V0 contains reviewable VI/EN Markdown, structured JSON, input/output and evaluation references, versions/hashes, warnings and review status. A pre-approval package is NOT an approved ContentVersion or publishing authorization. Bind final approval to the exact reviewed bytes; then create ContentVersion through the canonical path. Any later content edit requires the relevant checks and approval again.

M1 is not achieved by merged modules, green CI, historical artifacts absent from the active DB, or a model's self-rating. It requires real local artifacts and Founder's final approval.

## 5. Diagnose before changing a gate

Classify a blocked execution by layer: outer execution permission; CLI version/auth/capability; ContentEngine input/state validation; provider/transport; content/schema validation. Record the exact sanitized error code, last started/completed step, command shape, observed counters and expected result.

An outer policy denial is not evidence of a code bug. Stop and seek an explicitly permitted execution environment/permission decision; do not disguise commands, disable safeguards, change provider/model or repeatedly retry a denied action. Preserve unknown causes as unknown. Fix the smallest proven defect and add a focused regression for it.

No automatic retry for authorization/configuration failures. Transient retries and content repairs stay within existing approved budgets. A repair needs an actionable diagnosis; repeating an unchanged failing input is not a learning loop. Do not weaken an evaluator simply to make one article pass.

## 6. Local operating contract

Preserve the current operational DB, named volume and compose project during M1. Inspect before changing. Never use test resets, `docker compose down -v`, volume deletion or forced checkout/reset on operational data. Never overwrite an existing `.env` during setup. Never log its contents.

`DATABASE_URL` is operational data; `TEST_DATABASE_URL` must resolve to a distinct disposable DB before any destructive test. CI/test fixtures must never target the operational DB. For a schema change, require explicit migration permission, a verified backup, applicable migration tests and a recovery plan before touching real data. Code rollback alone is not a DB rollback.

Use the current single checkout for M1. If simultaneous development later causes interference, use a separate development worktree only with an explicit task; keep its test DB/artifacts separate and do not start a second compose project against the operational volume. This is optional, not an M1 dependency. Do not switch deployed code while a runtime step is executing; reach a safe checkpoint first.

Local-only target: application and DB ports bound to loopback, no public exposure or port forwarding by default. Existing development defaults are not proof that this is enforced. Verify actual binding/exposure; fix a demonstrated exposure immediately, otherwise schedule the small binding/configuration patch with M2. Local secrets and operational data remain outside Git.

Before repeated operational use, add a backup procedure and demonstrate restore into a SEPARATE disposable destination. Verify representative lineage/artifact links without altering the active runtime. No dump in GitHub. Document the last usable recovery point rather than promising zero data loss.

## 7. M2 - the smallest operator surface

After M1, wrap existing services/scripts with a thin Journal entrypoint: status, read-only preflight, bounded resume, export. These are proposed operations, NOT commands that already exist. No second state machine, scheduler or orchestration engine.

Status must expose the current step, pending human decision, blocker, remaining budget, relevant artifact refs and the next allowed action. Resume must reuse committed artifacts, respect exact approvals and stop on changed inputs. Export must reproduce the same approved/review package from the same frozen content without another model call.

Acceptance: three distinct real bilingual Journal cases in total, including M1; the last two complete on the same merged runtime version without case-specific code edits. Include one safe stop/restart/resume demonstration without duplicate confirmed side effects. Record exact tested versions; no undocumented one-off SQL to make a case pass.

Choose optimizations from evidence. Current review candidates include duplicated Angle input, missing sanitized CLI diagnostics, usage extraction and error-specific retries. These are investigation items, not verified root causes or mandatory pre-M1 refactors. Unknown usage/cost stays unknown, not zero.

## 8. Quality inputs and learning without overbuilding

Before new cases, define one reader, one question, expected useful result and appropriate next action. Supply confirmed MOTGU material and a small approved positive/negative calibration set. Use existing OriginalityPack/settings structures. Do not fabricate originality or turn founder hypotheses into customer facts.

Capture a minimal per-run record using existing models/artifacts where possible: case/run/content version; code and prompt/recipe/evaluator versions; settings/context/evidence hashes; model/tool calls, durations and known usage; failure/retry reasons; original/revised/final content; human edit time/category; approval and final package identity. Do not add a new metrics platform merely to collect this record.

Three loops:

1. Per run: observe -> classify -> smallest fix -> regression -> rerun. Start now.
2. Per editorial batch: compare good AND weak outputs, human edits and evaluator false positives/negatives. Change one major variable at a time on frozen inputs. Keep holdout cases out of tuning. Human review and hard gates control promotion; retain rollback to the prior version.
3. After publication: connect URL + ContentItem/Version + hypothesis to measured exposure, reader actions and inquiries. Keep alternative explanations and negative evidence. Missing traffic is INCONCLUSIVE, not proof of no demand.

A 10-20-item batch or 1/3/6-month review is an organizing cadence, not automatic statistical sufficiency. Automate memory/ranking/summaries only when measured retrieval, duplicate intent, repeated edit burden or volume warrants it. Golden examples are human-approved, diverse and versioned; generated prose never becomes factual evidence by itself.

## 9. M3/M4 and explicit deferrals

M3 introduces a small manual Journal handoff and measurement identity after M1/M2. It may take a deliberately scoped slice of CE08 before full CE06/CE07, without claiming those phases complete. Full WordPress integration, Artwork work and analytics adapters remain separately scoped. Never overwrite externally edited web content without reconciliation.

M4 expands regression/memory/learning based on actual data, not a calendar deadline. Per-run observations start now; a later M4 gate does not mean postponing basic feedback capture. No automatic prompt/rule promotion or publication.

Freeze provider expansion, broad refactors, large dashboards, generic automation, full Memory Tree and speculative CI optimization until a named bottleneck and acceptance test justify them. A security/data-integrity defect can interrupt this order; cosmetic polish cannot.
