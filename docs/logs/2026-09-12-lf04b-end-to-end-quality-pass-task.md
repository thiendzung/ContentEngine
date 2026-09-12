# LF-04B — End-to-end bilingual quality pass

Date: 2026-09-12
Owner: Founder for model-backed commands; Agent Local for final read-only verification; MG for review.
Status: NOT EXECUTED.

## Objective

Finish the remaining quality path for the first real M1 Journal using the already-generated immutable VI/EN drafts:

`bounded Review/Revise -> Assertion Audit v5 -> Source-copy v2 -> STOP for MG review`

Do not regenerate Angle, Outline or Writer v1 drafts. Do not create Operational Package, final approval, ContentVersion or publishing records in this task.

## Exact starting state

Shared approved Outline:

- artifact `49fae9fc-44f8-460c-a805-bba2c5a5b6e6`, v1;
- hash `ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979`;
- OutlineApproval `233e07d6-46dd-4d58-bd01-0f6cac6464f5` remains valid.

VI:

- Writer run `66046633-bf57-41a8-bb80-7a60058bf7f9`;
- source draft artifact `07c2176a-0d77-4ef8-a90d-6d541b2a10c2`, v1;
- source draft hash `3ff54295c8179ba431562120b33bf6450f1befcbcee08d109a5cf9a34ad5dced`.

EN:

- Writer run `80529fb8-afef-482f-9d54-b4a866ecaf1b`;
- source draft artifact `0a48779d-bd73-4b61-8aec-2715178e2514`, v1;
- source draft hash `35deb36fe8fc98fe5026f81f73cea1511c95b1ff4e8909f07a77c493200af916`.

Expected route for model-backed stages: exact `codex_cli / gpt-5.6-luna` using repository-approved `codex-cli 0.154.0-alpha.6.2`, cached auth, no-tool controls, read-only sandbox, web disabled, ignored user config and ephemeral execution.

## Editorial targets carried into Review/Revise

The existing approved Review/Revise prompts already require native-language clarity, removal of internal/technical wording, exact support-ref preservation, no new research/facts and zero unresolved factual claims. MG additionally reviews the resulting immutable revisions against these observed defects:

1. VI must no longer contain the token `سواء` or any other stray non-Vietnamese fragment.
2. EN must remove reader-facing internal wording such as `current canonical information`.
3. Comparable/private-sales wording must remain context, not imply guaranteed buyer access to private-sale data and not become a self-valuation formula.
4. `relative importance`, quality and market/appraisal concepts must be clearly contextual rather than instructions for a novice to self-appraise.
5. Subject matter remains one contextual factor and must not become a standalone price rule.

These are post-execution editorial checks. Do not hand-edit the immutable artifacts.

## Model and retry budget

For each locale:

- Review/Revise: one outer CLI invocation; `ReviewReviseGenerator(max_attempts=2)` may make at most 2 ModelCalls only for structured-output validation retry.
- Assertion Audit: one outer CLI invocation only after successful Review/Revise; `AssertionAuditGenerator(max_attempts=2)` may make at most 2 ModelCalls only for structured-output validation retry.
- Source-copy v2: deterministic, zero ModelCalls, zero provider calls, zero ToolCalls.

Across both locales, maximum new model calls is 8 if every structured-output stage needs its one internal retry. No outer/manual rerun is authorized.

If VI fails at any model-backed stage, STOP before EN and report. If VI completes the full quality block, run EN once. If EN fails, preserve the completed VI lineage and STOP.

Assertion Audit acceptance per locale:

- `audit_result != fail`;
- `critical_unsupported_count = 0`;
- `critical_contradicted_count = 0`.

Non-critical warnings are allowed but must be preserved verbatim.

Source-copy acceptance per locale:

- `summary.fail_count = 0`.

Warnings are allowed but must be preserved verbatim.

## Execution — Founder, from `backend/`

Run the VI block exactly once. It uses only existing production CLIs, parses their structured stdout locally and stops automatically if a hard gate fails. Temporary JSON files stay under `/tmp` and must never be committed.

```sh
set -euo pipefail
export PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH"
TMP="/tmp/lf04b-vi-$$"
mkdir -p "$TMP"

.venv/bin/python scripts/review_revise_real_o4_journal_draft.py \
  --writer-run-id 66046633-bf57-41a8-bb80-7a60058bf7f9 \
  --source-draft-artifact-id 07c2176a-0d77-4ef8-a90d-6d541b2a10c2 \
  --source-draft-version 1 \
  --source-draft-hash 3ff54295c8179ba431562120b33bf6450f1befcbcee08d109a5cf9a34ad5dced \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna > "$TMP/review.json"
cat "$TMP/review.json"

.venv/bin/python - "$TMP/review.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["ready_for_assertion_audit"] is True
assert p["unresolved_factual_claim_count"] == 0
PY

REVISED_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_artifact_id"])' "$TMP/review.json")
REVISED_VERSION=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_version"])' "$TMP/review.json")
REVISED_HASH=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_hash"])' "$TMP/review.json")

.venv/bin/python scripts/assert_real_o4_journal_draft.py \
  --writer-run-id 66046633-bf57-41a8-bb80-7a60058bf7f9 \
  --revised-draft-artifact-id "$REVISED_ID" \
  --revised-draft-version "$REVISED_VERSION" \
  --revised-draft-hash "$REVISED_HASH" \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --locale vi-VN \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna > "$TMP/audit.json"
cat "$TMP/audit.json"

.venv/bin/python - "$TMP/audit.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["audit_result"] != "fail"
assert p["critical_unsupported_count"] == 0
assert p["critical_contradicted_count"] == 0
PY

AUDIT_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_artifact_id"])' "$TMP/audit.json")
AUDIT_VERSION=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_version"])' "$TMP/audit.json")
AUDIT_HASH=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_hash"])' "$TMP/audit.json")
AUDIT_EVAL_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["quality_evaluation_id"])' "$TMP/audit.json")

.venv/bin/python scripts/source_copy_real_o4_journal.py \
  --locale vi-VN \
  --writer-run-id 66046633-bf57-41a8-bb80-7a60058bf7f9 \
  --source-draft-artifact-id "$REVISED_ID" \
  --source-draft-version "$REVISED_VERSION" \
  --source-draft-hash "$REVISED_HASH" \
  --assertion-audit-artifact-id "$AUDIT_ID" \
  --assertion-audit-version "$AUDIT_VERSION" \
  --assertion-audit-hash "$AUDIT_HASH" \
  --assertion-audit-quality-evaluation-id "$AUDIT_EVAL_ID" \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 > "$TMP/source-copy.json"
cat "$TMP/source-copy.json"

.venv/bin/python - "$TMP/source-copy.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["summary"]["fail_count"] == 0
PY

echo "LF-04B VI QUALITY BLOCK PASS — outputs: $TMP"
```

Only if the VI block exits successfully, run the EN block exactly once:

```sh
set -euo pipefail
export PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH"
TMP="/tmp/lf04b-en-$$"
mkdir -p "$TMP"

.venv/bin/python scripts/review_revise_real_o4_journal_draft.py \
  --writer-run-id 80529fb8-afef-482f-9d54-b4a866ecaf1b \
  --source-draft-artifact-id 0a48779d-bd73-4b61-8aec-2715178e2514 \
  --source-draft-version 1 \
  --source-draft-hash 35deb36fe8fc98fe5026f81f73cea1511c95b1ff4e8909f07a77c493200af916 \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna > "$TMP/review.json"
cat "$TMP/review.json"

.venv/bin/python - "$TMP/review.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["ready_for_assertion_audit"] is True
assert p["unresolved_factual_claim_count"] == 0
PY

REVISED_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_artifact_id"])' "$TMP/review.json")
REVISED_VERSION=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_version"])' "$TMP/review.json")
REVISED_HASH=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["revised_draft_hash"])' "$TMP/review.json")

.venv/bin/python scripts/assert_real_o4_journal_draft.py \
  --writer-run-id 80529fb8-afef-482f-9d54-b4a866ecaf1b \
  --revised-draft-artifact-id "$REVISED_ID" \
  --revised-draft-version "$REVISED_VERSION" \
  --revised-draft-hash "$REVISED_HASH" \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 \
  --locale en \
  --expected-provider codex_cli \
  --expected-model gpt-5.6-luna > "$TMP/audit.json"
cat "$TMP/audit.json"

.venv/bin/python - "$TMP/audit.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["audit_result"] != "fail"
assert p["critical_unsupported_count"] == 0
assert p["critical_contradicted_count"] == 0
PY

AUDIT_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_artifact_id"])' "$TMP/audit.json")
AUDIT_VERSION=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_version"])' "$TMP/audit.json")
AUDIT_HASH=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["assertion_audit_hash"])' "$TMP/audit.json")
AUDIT_EVAL_ID=$(.venv/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["quality_evaluation_id"])' "$TMP/audit.json")

.venv/bin/python scripts/source_copy_real_o4_journal.py \
  --locale en \
  --writer-run-id 80529fb8-afef-482f-9d54-b4a866ecaf1b \
  --source-draft-artifact-id "$REVISED_ID" \
  --source-draft-version "$REVISED_VERSION" \
  --source-draft-hash "$REVISED_HASH" \
  --assertion-audit-artifact-id "$AUDIT_ID" \
  --assertion-audit-version "$AUDIT_VERSION" \
  --assertion-audit-hash "$AUDIT_HASH" \
  --assertion-audit-quality-evaluation-id "$AUDIT_EVAL_ID" \
  --outline-artifact-id 49fae9fc-44f8-460c-a805-bba2c5a5b6e6 \
  --outline-artifact-version 1 \
  --outline-artifact-hash ba556fc7026295ef0f660b2773ac4cd7c4d3df89b7aab6cb9d5a01af24419979 > "$TMP/source-copy.json"
cat "$TMP/source-copy.json"

.venv/bin/python - "$TMP/source-copy.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["summary"]["fail_count"] == 0
PY

echo "LF-04B EN QUALITY BLOCK PASS — outputs: $TMP"
```

Do not rerun either block. If any assertion or command exits non-zero, preserve the runtime state and report the exact sanitized failure to MG.

## Agent Local post-verification

After Founder reports both blocks completed successfully, Agent Local performs read-only verification only.

Return per locale:

- Writer run final status/failure fields;
- exact Review/Revise StepRun, ContextManifest, ModelCalls and revised `journal_draft` artifact ID/version/hash;
- full persisted revised visible draft;
- assertion-audit eval run, handoff, StepRun, ContextManifest, ModelCalls, artifact ID/version/hash, QualityEvaluation ID/result;
- exact `audit_result`, unsupported/contradicted counts, critical unsupported/contradicted counts;
- every non-critical audit warning/finding verbatim;
- source-copy eval run, handoff, StepRun, artifact ID/version/hash, QualityEvaluation ID/result;
- full source-copy `summary` and every warning/finding verbatim;
- verify source-copy ModelCalls/provider calls/ToolCalls are zero;
- total ModelCall counts and runner versions actually persisted;
- verify original v1 Writer drafts remain immutable;
- verify source run, bundle, SettingsSnapshot, EvidenceSet, OriginalityPack, Angle/Approval, Outline/Approval remain unchanged;
- verify no Operational Package, final approval, ContentVersion or publishing records exist.

Editorial post-check on the revised visible copy:

- VI contains no `سواء` or stray foreign-language token;
- EN contains no internal implementation wording such as `canonical information`;
- comparable/private-sales phrasing does not promise access or become a formula;
- appraisal concepts remain contextual;
- subject matter remains one factor;
- both locales remain independent and natural;
- no invented MOTGU/current-artwork/investment/scarcity/status claims.

Success status:

`STATUS: LF-04B QUALITY PASS COMPLETE — READY FOR MG REVIEW / LF-04C`

Then STOP.

Do not create Operational Package or ask for final Founder approval until MG reviews the complete revised drafts and warning set.