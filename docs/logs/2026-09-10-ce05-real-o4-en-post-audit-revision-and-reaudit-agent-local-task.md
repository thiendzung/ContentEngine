# CE05-T05.14-EN-POST-AUDIT-REVISION-AND-REAUDIT-LOCAL

Owner: **Agent Local**

## Objective

After the implementation PR is merged, execute the exact English post-Assertion-Audit
revision and re-audit for the locked CE05 Journal candidate. Do not rerun or revise
Vietnamese and do not start T05.15.

## Mandatory local synchronization

Before reading any task file or running local code:

```bash
git status --porcelain
```

Unexpected local changes are `BLOCKED`. Do not reset, stash, delete or overwrite them.

Then synchronize clean `main` with canonical GitHub, verify `HEAD == origin/main`, and
confirm the merged post-audit revision implementation is present.

## Locked inputs

```text
ContentCase: 9ec6133b-5f14-46d0-9866-e3b049e537b5
Outline: 39e0a6a3-d735-432b-9353-1da8314b72cd / v1 / 4f4a746bc4b10625be50b5cc4c2311cad7a1ebee5797bcde8058c622eed351ea
EvidenceSet: c5d46edb-3557-4efb-a479-8dd5702ae6c9 / v8 / locked / 83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a
OriginalityPack: 6bd287ec-43f9-4d69-957c-2223f258f909 / approved / d2f193a68b8454114f18dff4d65e5c8b26c494636e1200e55a3fb4c6797eb238
SettingsSnapshot: 8f687d1c-1cba-4571-8960-77d7faf18453 / d26829305c979d6cb8bd0f6ae72d795d6c21ca2c5eae9f5c3e6bf3ef0d8a176c
VI PASS audit Artifact: a1525323-e8d9-4eb4-be72-3837487739e9 / v1 / a77537ea4f1fcf97b374b2638769490be84e3a8424a002c60e25fb845ea25966
VI QualityEvaluation: 11dac071-ceef-4204-a1b5-24b8e58ebe0f
EN LocaleVariant: 19d6b5e8-8ed9-4e3c-b9e3-69add06b09bc
EN Writer run: b2e86caf-a7a2-463a-8c8c-9e94e02272f5
EN source draft v2: d512f3f4-bc28-473b-9de1-f0a838940191 / e65472ebb266a0a62ef1d4d855fefb36d23a72e28eeedbbd30acbec7fe1bc034
EN failed v3 audit Artifact: e89ba535-83d3-48fd-a17d-6150e67a21b2 / v1 / e75290894c621f431a51885e1ddc8a7c40cb45bb1cc6dfac8a85917c86f52831
EN failed QualityEvaluation: 108d887d-639d-4326-846d-1b925005f5e6
Provider/model: codex_cli / gpt-5.6-luna
```

The English audit Artifact and QualityEvaluation must still contain exactly the five
persisted unsupported findings required by the implementation contract. Any mismatch is
`BLOCKED`; do not repair records.

## Exact sequence

```text
sync clean main
→ preflight locked VI PASS and EN v2/audit FAIL inputs
→ apply/verify migration 20260910_0022
→ verify journal_post_audit_revise_en:v1 and journal_post_audit_revise_en_v1:v1
→ execute the exact EN post-audit revision CLI once
→ execute the identical EN revision command again
→ verify same v3 artifact, reuse=true, model_attempts=0 and zero extra side effects
→ execute the existing T05.14 Assertion Audit v3 CLI against exact EN v3
→ execute the identical EN audit command again
→ verify audit reuse=true, model_attempts=0 and zero extra side effects
→ verify VI PASS artifact/evaluation and all upstream lineage remain unchanged
→ report full EN v3 draft and full EN v3 assertion audit
→ STOP
```

The revision CLI must be run from `backend/` with the exact IDs and hashes above. Its
second invocation must reuse the same English Writer run and immutable v3 artifact. The
audit CLI must use the exact existing command contract in
`docs/logs/2026-09-10-ce05-real-o4-assertion-audit-agent-local-task.md`, substituting
only the new EN v3 artifact ID/version/hash returned by the revision CLI.

## Acceptance gates

Revision:

- same existing EN `localize` Writer run; no new Writer ContentRun;
- source v2 remains unchanged;
- one immutable EN `journal_draft` v3;
- all five persisted findings are remediated;
- non-target copy, structure and support refs remain identical;
- no Evidence/Originality ref, research, URL, Search, ToolCall, sibling draft or translation;
- exact rerun reuses v3 with `model_attempts=0` and no additional records.

Re-audit:

```text
EN audit_result = pass
EN unsupported_count = 0
EN contradicted_count = 0
EN critical_unsupported_count = 0
EN critical_contradicted_count = 0
```

If the completed audit returns `warn` or `fail`, report `NEEDS CHANGES` and do not revise
again. Infrastructure, lineage, registry, schema, hash or runtime mismatches are
`BLOCKED`. Do not rerun VI or start T05.15.

## Required report

```text
TASK ID: CE05-T05.14-EN-POST-AUDIT-REVISION-AND-REAUDIT-LOCAL

START STATE
MIGRATION / REGISTRY
INPUT PREFLIGHT
REVISION FIRST EXECUTION
FULL EN V3 DRAFT
REVISION IDEMPOTENCY
EN ASSERTION AUDIT V3
FULL EN V3 ASSERTION AUDIT
AUDIT IDEMPOTENCY
VI PASS IMMUTABILITY
UPSTREAM IMMUTABILITY
COUNTS / SIDE EFFECTS
TESTS / PROBES
RISKS / BLOCKERS
STATUS: READY FOR REVIEW | BLOCKED | NEEDS CHANGES
```

After reporting, stop.
