# AO-D0 - MG review of Founder-relayed local baseline

Review date: 2026-09-16
Task: AO-D0
Executed specification ref: `05f40ccd4bc18c0c39fd5db97a0f4a9bc51ec5dc`
Disposition: ACCEPTED AS A COMPLETED READ-ONLY BASELINE REPORT, WITH QUALIFICATIONS
Production readiness: NOT PROVEN; AO-1/AO-2 remain required

## Evidence boundary

Founder pasted Agent Local's AO-D0 report into the project conversation. MG reviewed it against the exact task, spec and live GitHub/code. This is the first returned AO-D0 report, not a direct MG-to-agent conversation. Local observations below are attributed to Agent Local; MG did not inspect the Founder machine or independently rerun its commands.

The report states FILES CHANGED=NONE, MODEL CALLS=0, no DB connections, no service changes and no commit/push. Its declared scope matches AO-D0. Raw command transcripts and an exact observation timestamp were not supplied. The baseline is adequate for planning, not proof of current process liveness, absent side effects or enforced isolation. Revalidate time-sensitive identifiers before any later action; do not repeat the whole survey merely to obtain another report.

## Local observations accepted as reported

| Area | Reported observation | Interpretation / boundary |
|---|---|---|
| Primary checkout | Local main `acf0de5`; reported 548 commits behind fetched main | A retained checkout, not the deployment identity of every process; no reset or fast-forward authorized. |
| Fetched main | `5eef4e72cb15bc6ea30488a15f18a5de091053d6` after F3/#104 | Matches GitHub main at this review. |
| Primary dirty files | `frontend/next-env.d.ts`, `frontend/tsconfig.json` | Preserve both. Attribution to automatic Next.js updates is reported, not independently established. |
| F4 worktree | `/private/tmp/contentengine-f4-i1-20260916`, based on `ba9c3ed913cd1a24dce380035c16d0fe6cd472d1` | Active uncommitted work exists locally; it is not yet a GitHub-reviewed implementation. |
| F4 changed paths | Modified operator_runtime.py, operator_view.py, operator_writers.py, run_operator_worker.py, test_operator_writers.py; untracked operator_quality.py, operator_quality_worker.py, test_operator_quality.py | Names abbreviated here; original report is the source. Preserve scope and owner; do not start a competing F4 writer. |
| Default API/UI/worker | API on 8000, UI on 3000 and worker-loop from a retained F0 worktree | Not proof of current main/F3/F4 deployment. Current frontend API destination and each process's effective DB binding remain unverified. |
| Other API | API on 8003 from F3 acceptance worktree | Not automatically the production endpoint. |
| Operational resource | `contentengine-postgres-1` on loopback 5432 | Identified from metadata only. Operational DB contents/schema were not queried. |
| Test resources | 11 PostgreSQL test containers on loopback 55432-55442; F4 instance on 55442 | Resource inventory, not permission to reset/remove/reuse them. Names/ports alone do not establish effective application DB binding. |
| Schema | Last documented operational 0027, code/test baseline 0034 | Actual operational schema UNKNOWN. |

Reported PID values are intentionally not promoted to persistent operating instructions. Any service stop/rebind requires a new identification of PID/start time/owner/worktree/target and separate authorized maintenance scope. No process kill, test reset, volume deletion or operational query is authorized here.

Multiple worktrees and isolated test instances can be intentional. Their presence is not itself a defect. The actionable risk is confusing a retained F0 service with the release under test. Do not erase useful evidence merely to make the environment look tidy.

## Capability interpretation

| Capability | Evidence in report | MG disposition |
|---|---|---|
| Codex binary/version | `/Applications/ChatGPT.app/Contents/Resources/codex`, `0.154.0-alpha.6.2` | Installation/version reported observed. |
| Codex non-interactive invocation | `exec` appears in local help; prior F3 acceptance separately used Codex for Writer stages | Candidate for restricted integration. Does not prove production controller isolation. |
| Codex app-server/exec-server/remote-control/resume/queue | Report refers to help output; no lifecycle test | Advertised interface only. Persistent controller recovery remains UNPROVEN. Do not execute a guessed command from this inventory. |
| Antigravity | App version 2.12.2; `agy` symlink target missing | That installed CLI path is unavailable as observed. Other supported interfaces and persistent automation remain UNPROVEN, not globally impossible. |
| Secret/API isolation | No restricted profile or denial tests provided | UNPROVEN for both applications. A named profile, filesystem sandbox label or transcript file is not boundary proof. |

AO-3 stays optional. No symlink repair, installation, login, daemon activation or provider switch is needed merely to close AO-D0.

## Required corrections to the report's interpretations

### 1. TEST configuration is not a blind DATABASE_URL override

At inspected main, `backend/app/core/database.py` creates the engine from `Settings.resolved_database_url`. `backend/app/core/config.py` requires `TEST_DATABASE_URL` in `APP_ENV=test` and rejects an identical application/test target. In non-test mode it selects `DATABASE_URL`.

Therefore a later authorized test task must use `APP_ENV=test` plus the explicit isolated `TEST_DATABASE_URL`, retain a distinct application/operational identity for guard comparison, and verify the resolved target before test writes. Do not repoint both variables to the same database or replace the developer .env. Follow the candidate's canonical test preparation guards. Port 5432 is neither permission nor sufficient proof of a database's role.

This correction is code-reviewed; actual running-process configuration is still UNKNOWN because AO-D0 did not inspect secret-bearing environments or connect to DBs.

### 2. Spec baseline is not a claimed single local deployment

The spec task explicitly permitted reporting retained worktrees/new work and described its main SHA as a dated repository observation. The reported source/runtime differences refine the baseline; they do not require all local checkouts to be synchronized immediately.

### 3. Hardcoded founder is an authorization gap, not an identity mechanism

The inspected Journal command/decision and legacy review handlers pass `actor_id="founder"`. The application entrypoint exposes observability and CORS middleware, not a demonstrated reviewer/operator authentication boundary. This establishes a code-review gap, not a performed exploit or proof of external network exposure.

Merely accepting a client role or renaming the field cannot fix this. AO-1 must derive identity server-side, deny agent access to human decisions and check alternate routes. Exact artifact hashes guard data integrity; they do not establish who is allowed to approve it.

### 4. A proxy alone is not credential/OS isolation

An HTTP allowlist can restrict one route, but cannot by itself prevent an unrestricted process reading .env, reviewer profiles, DB credentials, inherited environment, live repository files or Docker/privileged control interfaces. Direct access to another backend port can also bypass a proxy-only policy.

AO-1 must prove the combined server authorization, process/filesystem/credential boundary and direct-path denial. Prefer the smallest enforceable implementation; a new proxy is optional, not a substitute for those tests. Close or isolate alternate old runtimes through authorized maintenance before automatic operation, without interfering with active F4 work.

### 5. A model-native daemon is not required

Use a deterministic local supervisor with durable backend state and an approved restricted adapter. Existing workers invoke generation for allowed stages. Waiting/polling/continuation decisions do not need LLM calls. A persistent Codex chat, resume transcript or experimental daemon is not a prerequisite and does not replace backend checkpoints, grant checks or case ownership.

A logical OperatingGrant needs durable, versioned enforcement. Do not assume a new broad schema/service is necessary until existing storage is evaluated; any required migration is separately reviewed and does not enter F4 accidentally.

## Architecture and next-work disposition

- AO-D0 is complete as a read-only investigation. It does NOT pass any production capability, security, service or pilot acceptance test.
- Continue the existing F4 package under its already-dispatched scope and owner. No second implementation, cleanup or ref change is dispatched by this review.
- MG can design AO-1 from this evidence while F4 implementation remains the one active code stream. Implementation order remains F4 -> F5.1 -> AO-1 -> F5.2 -> AO-2 -> reviewer UI/minimum shell -> O1 -> real pilot.
- Before the next runtime proof, the F4 owner verifies its exact candidate and isolated target, not the default F0 8000/3000 services. Backend/frontend destination/worker/repo/config identities must agree. Include this verification in the existing proof packet, not a new per-command paperwork loop.
- Before autonomous release, a maintenance task must classify retained services/resources, preserve evidence and establish one unambiguous supported release. No broad Docker prune, old-PID kill, operational volume deletion or root-worktree cleanup is authorized now.
- New acceptance cases S06/O03/A02 specify direct-path isolation, runtime identity mapping and advertised-vs-proven adapter capability. They are requirements, all NOT RUN by AO-D0.

## GitHub observations and code sources

- [main](https://github.com/thiendzung/ContentEngine/tree/5eef4e72cb15bc6ea30488a15f18a5de091053d6) matches the fetched F3 baseline.
- [PR #105](https://github.com/thiendzung/ContentEngine/pull/105) remained Draft at `ba9c3ed913cd1a24dce380035c16d0fe6cd472d1`, one contract file. Local uncommitted F4 work was not visible in that diff.
- [PR #106](https://github.com/thiendzung/ContentEngine/pull/106) remained Draft/unmerged at the executed SPEC_REF before this review update. Changing spec docs does not change the code/acceptance scope of #105.
- [Database binding](https://github.com/thiendzung/ContentEngine/blob/5eef4e72cb15bc6ea30488a15f18a5de091053d6/backend/app/core/database.py), [configuration/guards](https://github.com/thiendzung/ContentEngine/blob/5eef4e72cb15bc6ea30488a15f18a5de091053d6/backend/app/core/config.py), [application middleware](https://github.com/thiendzung/ContentEngine/blob/5eef4e72cb15bc6ea30488a15f18a5de091053d6/backend/app/main.py), [Journal routes](https://github.com/thiendzung/ContentEngine/blob/5eef4e72cb15bc6ea30488a15f18a5de091053d6/backend/app/modules/content_engine/journal/router.py).

MG actions in this review: GitHub/code/spec reads and documentation updates only. No local command execution, service change, DB access, model/research call, migration, acceptance activation or merge. The Founder-relayed report is received and reviewed; fresh machine agreement on this disposition has not been claimed.
