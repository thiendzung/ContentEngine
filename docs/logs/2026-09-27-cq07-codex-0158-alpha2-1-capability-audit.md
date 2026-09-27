# CQ-07 — Codex 0.158.0-alpha.2.1 capability audit

Date: 2026-09-27

Status:

`PASS_CQ07_CODEX_0158_IDENTITY_ADDENDUM`

`REPIN_ELIGIBLE_EXACT_VERSION_ONLY`

## Trigger

CQ-07 P01 real execution stopped fail-closed because the repository-approved runner
version remained:

`codex-cli 0.155.0-alpha.16.4`

while the installed ChatGPT-packaged runner resolved locally as:

`codex-cli 0.158.0-alpha.2.1`

No version-range relaxation, bypass, model call or runtime activation was used.

## Exact audited identity

- executable: `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`
- version: `codex-cli 0.158.0-alpha.2.1`
- SHA-256: `3e11ccc743e8198a5ef84fb57c89941d845b0ea0302485ed1fbac2f0821aca5a`
- file type: regular file, not symlink
- owner: `thiendung`
- mode: `-rwxr-xr-x`

## Command-surface audit

The exact binary preserved all ContentEngine runner-required surfaces:

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

All 21 current `CODEX_NO_TOOL_FEATURES` are present on the same exact binary.
Missing features: none.

## Authentication

`codex login status` succeeded using cached ChatGPT-session authentication.

No token, cookie or session material was printed or committed.

## Compatibility conclusion

No observed runner-contract break blocks the existing ContentEngine no-tool runner contract.
This audit authorizes only an exact repin to:

`codex-cli 0.158.0-alpha.2.1`

Ranges, wildcards and "latest" policies remain forbidden.

The exact-version check remains fail-closed.

## CQ-07 boundary

This audit and repin do not by themselves authorize:
- operational DB changes;
- production activation;
- publication;
- WordPress / Rank Math mutation;
- Pillar↔Cluster schema work.

Founder separately selected the isolated CQ-07 Angle route:

`codex_cli / gpt-5.6-luna`

Activation remains limited to the isolated CQ-07 pilot DB after focused repin verification.

## Side effects of the audit

- model/provider calls: 0
- DB mutation: 0
- operational DB touched: NO
- repository changes during the Agent Local identity audit: 0
- secrets printed: NO
