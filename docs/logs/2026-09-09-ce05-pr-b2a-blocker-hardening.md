# CE05 PR-B.2A — final Codex no-tool blocker closeout

Date: 2026-09-09

## Scope

Close the final PR #35 Codex no-tool blocker only. No real O4/model/provider call and no merge.

```text
Branch: ce05-model-runtime-activation
Start HEAD: b8eb1cacd1db699f95c50eaf037c8ba8d145ffa6
Implementation HEAD: 86b2ceb5f91626c54ba0b2a4853de1fd9495af4e
PR: #35
Migration: 20260909_0017 (existing; no migration created)
```

## Final blocker fix

Codex runtime is pinned to `codex-cli 0.153.4`; another installed version fails closed as
`agent_runner_version_not_approved` before capability/auth/model execution. The exact rust-v
0.153.4 feature list was audited and all required no-tool controls are checked before use:

```text
shell_tool
unified_exec
code_mode
view_image
shell_snapshot
multi_agent
apps
plugins
enable_mcp_apps
tool_suggest
in_app_browser
in_app_local_automation
browser_use
browser_use_full_cdp_access
browser_use_external
computer_use
remote_plugin
plugin_sharing
image_generation
skill_mcp_dependency_install
skill_search
```

Execution emits one explicit `--disable <feature>` pair for every feature above, plus
`-c web_search="disabled"`, `--ignore-user-config`, `--ephemeral`, isolated temporary cwd,
and `--sandbox read-only`. Missing capability fails closed as
`agent_tool_disable_unsupported`; API keys are excluded from the child environment.

The previous settings override, migration approval, and exact model provenance fixes remain
unchanged. No real O4/model/provider call was performed.

## Evidence

- Focused CE05 runtime tests: `15 passed`.
- Full backend: `359 passed`.
- Ruff: pass.
- mypy: pass.
- Migration round-trip `20260909_0017 → 20260909_0016 → 20260909_0017`: pass;
  test DB ended at `20260909_0017 (head)`.
- OpenAPI export: pass; no API contract change.
- Frontend lint, typecheck, and build: pass; generated build artifacts were not committed.
- CI: run `34355533154` / PASS; quality job `102479123153`.

## O4 read-only state

Application DB remained at `20260909_0016`; no application data was changed.

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked
EvidenceSet hash: 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved
OriginalityPack hash: d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
ContentRun: 0
journal_input_bundle: 0
angle_candidates: 0
AngleApproval: 0
ModelCall: 0
provider/tool calls: 0
```

Codex CLI support was verified locally at `codex-cli 0.153.4`; no model execution was run.

The O4 runtime counters remain:

```text
ContentRun: 0
journal_input_bundle: 0
angle_candidates: 0
AngleApproval: 0
ModelCall: 0
provider/tool calls: 0
NeedHypothesis: 530bdd27-f008-4910-9b3b-df83e007cfa2 = PROPOSED
```

## Status

`READY FOR FINAL RE-REVIEW`

PR #35 remains OPEN and unmerged.
