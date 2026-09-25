# A4E2C1 — Codex 0.155.0-alpha.16.4 capability audit

Date: 2026-09-25

Status:

`PASS_A4E2_CODEX_0155_ALPHA16_4_CAPABILITY_AUDIT`

`REPIN_ELIGIBLE_EXACT_VERSION_ONLY`

## Trigger

A4E2 exact-ref disposable lifecycle verification stopped fail-closed before runtime start because the repository-approved Codex CLI version was:

`codex-cli 0.155.0-alpha.16.3`

while the ChatGPT packaged executable resolved locally as:

`codex-cli 0.155.0-alpha.16.4`

No lifecycle bypass or version-range relaxation was used.

## Exact audited identity

- executable: `/Applications/ChatGPT.app/Contents/Resources/codex`
- version: `codex-cli 0.155.0-alpha.16.4`
- SHA-256: `93169e745735930598e867ad837abf3fdc50774a3ad7e7aa89c0d0c51b0189a5`
- regular file, not a symlink
- owner/mode reported: `thiendung:staff`, `-rwxr-xr-x`

## Command-surface audit

The exact installed binary preserved all ContentEngine runner-required surfaces:

- `exec`
- `--model`
- `--json`
- `--output-schema`
- `--output-last-message`
- `--sandbox`
- `--disable`
- `--skip-git-repo-check`
- `--ignore-user-config`
- `--ephemeral`
- config override `-c`
- stdin task input `-`

All 21 required explicit no-tool feature controls were present:

`shell_tool`, `unified_exec`, `code_mode`, `view_image`, `shell_snapshot`,
`multi_agent`, `apps`, `plugins`, `enable_mcp_apps`, `tool_suggest`,
`in_app_browser`, `in_app_local_automation`, `browser_use`,
`browser_use_full_cdp_access`, `browser_use_external`, `computer_use`,
`remote_plugin`, `plugin_sharing`, `image_generation`,
`skill_mcp_dependency_install`, `skill_search`.

## Authentication

`codex login status` exited successfully with cached ChatGPT-session authentication.

API-key-only authentication was not accepted or used. No token, cookie or session material was printed.

## Compatibility conclusion

No runner-contract break was observed between the previously approved `.16.3` contract and the audited `.16.4` binary. The only observed contract change was the exact version identity.

This audit authorizes only an exact repin to:

`codex-cli 0.155.0-alpha.16.4`

It does not authorize a wildcard/range/latest-version policy.

## Side effects

- model/provider calls: 0
- DB reads/writes: 0/0
- ContentEngine runtime starts: 0
- tracked repository changes during audit: 0
- binary/auth/config mutation: 0
- secrets printed: NO
- protected primary checkout changed: NO

A harmless warning reported that PATH aliases could not be created. No PATH or shim mutation occurred.
