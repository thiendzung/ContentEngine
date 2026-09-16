# AO-D0 - Local baseline and restricted-operator feasibility

Date: 2026-09-16
Status: READY FOR FOUNDER DISPATCH / READ-ONLY ONLY
Owner: Agent Local | Reviewer: MG
Specification: `../21-AGENT-OPERATED-JOURNAL-SPEC.md`
Task pack: `../AGENT-OPERATED-DELIVERY-TASKS.md`

## Goal

Return one fresh factual report so MG can implement the agent-operated product against the actual local environment. This is engineering reconciliation, NOT production operation and NOT proof the new spec is implemented.

Founder copies the accompanying prompt into the separate local-agent application. No delivery or execution is assumed from this file being present on GitHub.

## Exact ref policy

The dispatch prompt MUST supply SPEC_REF (the exact reviewed spec commit or verified merge containing it). Read this file and the linked spec/task pack from that ref using safe Git reads. You may fetch Git metadata, but do not switch/rebase/reset/stash an active checkout or move deployed code.

The last GitHub observation at spec creation was main `5eef4e72cb15bc6ea30488a15f18a5de091053d6`, after F3/#104 merged; F4/#105 had a contract at `ba9c3ed913cd1a24dce380035c16d0fe6cd472d1`. These are dated observations, not required local HEADs or permission to replace existing work. Report any newer work.

## Permission envelope

| Action | Permission |
|---|---|
| Read repo status/refs/files and fetch origin metadata | YES, no worktree switch |
| Read selected process/container/service metadata | YES, redact arguments/paths containing secrets |
| Read documented local version/help for already-present executables | YES, only commands known to be non-generating/non-mutating |
| Query operational DB or content rows | NO |
| Reset/query acceptance DB contents | NO; identify resources from safe metadata only |
| Start/stop/restart services; create volumes/worktrees; install/login | NO |
| Code/configuration/docs edit; commit/push/merge | NO |
| Browser Start/Continue/approve or worker claim | NO |
| Model/research/network service execution | ZERO calls |
| Operational migration/publish | NO |

Do not dump `.env`, full environment, cookies, raw process arguments, DB URLs, tokens or private content. Presence/absence or redacted identity is enough. Unknown information remains UNKNOWN.

## Required report

### A. Source and in-progress work

- Repository path/remote identity; current branch/HEAD and fetched origin/main.
- Known worktrees, clean/dirty status and dirty file names only; do not change them.
- Whether F4 or another task is currently active; report its exact local scope/SHA without interrupting it.
- Whether the inspected spec has been merged or is still a proposal.

### B. Local services and data boundary

- Which identified backend/frontend/worker/supervisor processes belong to ContentEngine and their loopback ports.
- Which data resources are production, test or unclassified from safe existing metadata; no DB connections in this task.
- Deployment ref or schema only when already reliably recorded; distinguish recorded observation from current measurement.
- Any reason a test task could accidentally point to production or an unclassified retained lineage.

### C. Agent capabilities and separation

For Codex and Antigravity separately, report VERIFIED / UNVERIFIED / UNAVAILABLE:

- installed executable/application version and evidence for a supported non-interactive or tool interface;
- whether it is merely an interactive session or a persistent service;
- supported way to restrict access to approved backend operations;
- whether reviewer browser credentials, deployment write access and operational DB secrets can be isolated from its production profile;
- known restart/cancellation/structured-output semantics, or UNKNOWN;
- what needs a separately authorized test. Do not invoke the model to investigate.

Do not assume a Pro subscription, app name or successful stage ModelCall proves an unattended safe controller.

### D. Reconciliation and next recommendation

- Differences from the spec's dated baseline.
- Minimum concrete prerequisites for AO-1/AO-2.
- Existing capabilities that can be reused; no framework redesign.
- Suggested next bounded task, but do NOT execute it.

## Stop and output

Stop after one report or on a permission/secret/unclassified-target issue. Preserve all work and services unchanged.

Output:
`AO-D0 / SPEC_REF / LOCAL REFS / FACTS / DIFFERENCES / CAPABILITY MATRIX / FILES CHANGED=NONE / MODEL CALLS=0 / NOT CHECKED / BLOCKERS / READY FOR REVIEW or BLOCKED / NEXT FOR MG`

Founder copies this report back to MG. MG reconciles it with live GitHub before future task dispatch. No automatic next task, production approval or migration follows from this report.
