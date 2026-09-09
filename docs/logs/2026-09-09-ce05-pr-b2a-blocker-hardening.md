# CE05 PR-B.2A — blocker hardening closeout

Date: 2026-09-09

## Scope

Fix PR #35 blockers only. No real O4/model/provider call and no merge.

```text
Branch: ce05-model-runtime-activation
Start HEAD: dd99eb255d290167d1c33af7362df1d4ad92b3b1
End HEAD: 1093234ada81f41f70b350ae7f15e6803721e997
PR: #35
Migration: 20260909_0017
```

## Fixes

1. Settings resolution now fails closed with `settings_override_policy_missing` when
   equal paths differ across SYSTEM, PROJECT, CONTENT_TYPE, LOCALE, or RUN_OVERRIDE.
   Equal values and disjoint paths remain valid.
2. Codex no-tool execution verifies CLI support for `--disable` and the required feature
   names, then explicitly disables `shell_tool`, `unified_exec`, `code_mode`, apps,
   plugins, MCP apps, and web search. The invocation retains `--ignore-user-config`,
   `--ephemeral`, isolated temporary cwd, and read-only sandbox.
3. Migration 0017 enforces non-empty `approved_by` for active SettingsVersion,
   PromptDefinition, and RecipeDefinition rows. Draft-to-active with approval is allowed;
   active payload mutation remains rejected.
4. Angle artifact model metadata is derived from the exact SettingsSnapshot route. A
   caller route mismatch fails closed before a model request.

## Evidence

- Focused CE05 runtime/Angle tests: `27 passed`.
- Full backend: `357 passed`.
- Ruff: pass.
- mypy: pass.
- Migration round-trip `20260909_0017 → 20260909_0016 → 20260909_0017`: pass;
  test DB ended at `20260909_0017 (head)`.
- OpenAPI export: pass; no API contract change.
- Frontend lint, typecheck, and build: pass; generated build artifacts were not committed.
- CI: run `34344664463`, job `quality`, PASS.

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

## Status

`READY FOR RE-REVIEW`

PR #35 remains OPEN and unmerged.
