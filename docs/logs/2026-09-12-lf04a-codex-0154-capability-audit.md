# LF-04A — Codex 0.154.0-alpha.6.2 capability audit

Date: 2026-09-12

STATUS: PASS / Founder-relayed Agent Local evidence.

LF-04A Phase A stopped fail-closed because the ChatGPT app bundled Codex CLI had changed from repository-approved `codex-cli 0.153.4` to `codex-cli 0.154.0-alpha.6.2`. No Writer command, ModelCall, ToolCall, migration or DB/runtime mutation occurred.

MG required a read-only capability audit before changing the exact version pin. Agent Local returned this sanitized result:

```json
{
  "auth_exit": 0,
  "cached_session_auth_ok": true,
  "disable_flag_supported": true,
  "exec_help_exit": 0,
  "features_exit": 0,
  "missing_required_features": [],
  "required_feature_count": 21,
  "supported_feature_count": 140,
  "version": "codex-cli 0.154.0-alpha.6.2",
  "version_exit": 0
}
```

Interpretation:

- exact installed version check succeeded;
- `codex exec --help` still exposes `--disable`;
- all 21 ContentEngine-required no-tool features remain explicitly disable-able;
- cached-session authentication is valid without API-key auth;
- no model execution was part of the audit.

This evidence authorizes only the smallest code change: replace the exact approved Codex CLI pin with `codex-cli 0.154.0-alpha.6.2` while retaining exact-version fail-closed behavior, no-tool capability verification, cached-session auth and all existing sandbox/web/tool restrictions.

It does not authorize a version range, wildcard, automatic latest-version acceptance, provider/model change, Writer execution, research, settings mutation or safety-control weakening.

After the pin change is merged and CI passes, LF-04A must rerun Phase A only before any Writer command.
