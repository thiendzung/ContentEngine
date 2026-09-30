# CQ-07 — Codex 0.159.0 capability audit

Date: 2026-09-30

Status:

`PASS_CQ07_CODEX_0159_CAPABILITY_AUDIT`

`REPIN_ELIGIBLE_EXACT_VERSION_ONLY`

## Trigger

The repository-approved Codex runner on main remained:

`codex-cli 0.155.0-alpha.16.4`

The current ChatGPT-packaged runner resolved as:

`codex-cli 0.159.0`

CQ-07 therefore remained fail-closed until the exact installed binary was audited.

## Exact audited identity

- executable: `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`
- version: `codex-cli 0.159.0`
- SHA-256: `ccd1b9441d35ce30102059c78514a125d676e6765ea1d001033e8cbe88718314`
- file type: regular file, not symlink
- owner: `thiendung:staff`
- mode: `755`
- Python `shutil.which("codex")`, `realpath`, `type -a`, and `which -a` resolved to the same executable.

The packaged wrapper was observed separately at:

`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`

with version `codex-cli 0.159.0` and SHA-256
`50ab38ba21d0d9f8346f32f41848382f15b556190f3c7a07e885a4fb73e379c8`.

The approved runtime identity is the resolved executable above, not the wrapper hash.

## Command-surface audit

Read-only checks:

- `codex exec --help`
- `codex features list`
- `codex login status`

Required execution surfaces were present:

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

All 21 current `CODEX_NO_TOOL_FEATURES` entries were present and none was reported as removed.

## Authentication

`codex login status` returned:

`Logged in using ChatGPT`

with exit code 0.

Cached ChatGPT/session authentication is therefore available. API-key-only authentication was not used.

## Authorization

This audit authorizes only an exact repository repin to:

`codex-cli 0.159.0`

Version ranges, wildcards, `latest`, or capability assumptions about another binary remain forbidden.

## Side effects

- model/provider calls: 0
- DB reads/writes: 0/0
- ContentEngine runtime starts: 0
- repository tracked changes during the Agent Local audit: 0
- binary/auth/config mutation: 0
- secrets printed: NO

Issue: #240.
