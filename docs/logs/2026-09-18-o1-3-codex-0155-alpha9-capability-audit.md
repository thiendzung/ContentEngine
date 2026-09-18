# O1.3 / #138 — Codex 0.155.0-alpha.9 capability audit

Date: 2026-09-18

STATUS: PASS / Founder-relayed Agent Local read-only evidence.

O1.3 controlled release lifecycle on PR #137 head `50e7b8a3a58b71ff02a4d0f10d0eaaefd7a258a6`
completed both startup/shutdown cycles safely, but post-release preflight stopped fail-closed because
the repository-approved Codex runner remained pinned to `codex-cli 0.155.0-alpha.2.6` while the
ChatGPT app bundled executable had updated.

The exact current executable was audited read-only before any repin:

- executable: `/Applications/ChatGPT.app/Contents/Resources/codex`;
- exact version: `codex-cli 0.155.0-alpha.9`;
- binary SHA-256: `2e0918e73319f9a57126a1bf04dcc778e1ff5c1804cac1cbff08ba0853f1c97b`;
- `codex exec --help`: exit 0 and `--disable` present;
- `codex features list`: exit 0;
- all 21 required `CODEX_NO_TOOL_FEATURES` names present;
- `codex login status`: exit 0, `Logged in using ChatGPT`;
- auth mode: cached ChatGPT session;
- model requests: 0;
- operational DB access: 0;
- repository mutations: 0.

Required no-tool features verified:

1. `shell_tool`
2. `unified_exec`
3. `code_mode`
4. `view_image`
5. `shell_snapshot`
6. `multi_agent`
7. `apps`
8. `plugins`
9. `enable_mcp_apps`
10. `tool_suggest`
11. `in_app_browser`
12. `in_app_local_automation`
13. `browser_use`
14. `browser_use_full_cdp_access`
15. `browser_use_external`
16. `computer_use`
17. `remote_plugin`
18. `plugin_sharing`
19. `image_generation`
20. `skill_mcp_dependency_install`
21. `skill_search`

Interpretation:

- the exact runner command surface used by ContentEngine remains compatible;
- all explicitly disabled unsafe/no-tool surfaces remain addressable;
- cached ChatGPT authentication remains valid;
- no evidence justifies a version range, wildcard, latest-version acceptance or bypass.

This audit authorizes only the bounded exact repin from:

`codex-cli 0.155.0-alpha.2.6`

to:

`codex-cli 0.155.0-alpha.9`

while preserving:

- exact-version fail-closed behavior;
- preflight before capability/auth/model execution on mismatch;
- all 21 explicit no-tool feature checks;
- read-only sandbox;
- web search disabled;
- ignored user config;
- ephemeral execution;
- cached-session authentication;
- existing provider/model routing authority.

After the repin is merged into the O1.3 branch, CI and exact-ref OCR must pass before any lifecycle
retry. This audit does not authorize model execution, publication, O1.4, operational DB mutation or
a lifecycle retry.
