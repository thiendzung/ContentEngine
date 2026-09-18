# F6.A1-R1 — Codex 0.155.0-alpha.2.6 capability audit

Date: 2026-09-18

STATUS: PASS / Founder-relayed Agent Local evidence.

F6.A1 Issue #118 stopped fail-closed on exact merged main `0c3ae7f3214dbdb381dacbddd38fb4e36dc5b41a` because the ChatGPT app bundled Codex CLI had changed from repository-approved `codex-cli 0.154.0-alpha.6.2` to `codex-cli 0.155.0-alpha.2.6`.

No browser acceptance, model execution, ToolCall, content-case creation, code change or DB mutation occurred before the stop.

Issue #120 then performed the required read-only capability audit of the exact executable that F6.A1 would resolve:

- executable: `/Applications/ChatGPT.app/Contents/Resources/codex`;
- exact version: `codex-cli 0.155.0-alpha.2.6`;
- binary SHA-256: `805f2102d573c580d8cad2fc774b81837e68f7e9bdd1adb559d67801bbc1f9bd`;
- `codex exec --help`: exit 0, all runner-required flags present;
- `codex features list`: exit 0, current parser resolves all 21 required no-tool feature names;
- `codex login status`: `Logged in using ChatGPT`, cached-session auth, no API-key auth;
- exact audit lane: `0c3ae7f3214dbdb381dacbddd38fb4e36dc5b41a`, clean;
- ModelCalls: unchanged;
- ToolCalls: unchanged;
- no DB mutation;
- protected Founder checkout unchanged.

Interpretation:

- the CLI command surface used by ContentEngine remains compatible;
- every explicitly disabled unsafe/no-tool feature required by the runner remains addressable;
- cached ChatGPT authentication remains valid;
- no evidence justified a version range, wildcard, latest-version acceptance or bypass.

This evidence authorizes only the bounded exact-version repin from:

`codex-cli 0.154.0-alpha.6.2`

to:

`codex-cli 0.155.0-alpha.2.6`

while preserving:

- exact-version fail-closed behavior;
- preflight before authentication/model execution on mismatch;
- read-only sandbox;
- all 21 explicit `--disable` feature controls;
- web search disabled;
- ignored user config;
- ephemeral execution;
- cached-session authentication;
- existing provider/model routing authority.

After the repin PR is merged, F6.A1 must rerun exact-main preflight before any model call. The capability audit itself does not authorize publication, F5.2, WordPress, operational DB writes or any workflow expansion.
