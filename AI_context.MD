# AI_context.MD - ContentEngine shared working window

## Current WIP — #368 QA test-environment cleanup

QM-02E Founder UI is complete. Founder merged PR #370 from verified head
`d6212af0320682216e19cfdda1079473b72fa2b4`; current GitHub main is
`99385a36cd0ef4e414fd1404c3e8aee4117b4d1f`. Issue #360 is closed and #361 Golden E2E is
unblocked.

Before Golden E2E, #368 removes the remaining ambient test-environment coupling so the final
full-suite proof has a clean baseline.

Active branch:
`fix/qa-test-environment-isolation`

Active PR:
#371

Bounded QA scope:
- use the runtime-resolved dedicated test DB target instead of a stale test-only fallback;
- direct Settings tests explicitly control app_env / DB inputs relevant to the assertion;
- positive provider tests explicitly provide synthetic keys;
- negative provider tests explicitly set provider keys to absent;
- affected tests must pass both with and without ambient developer provider secrets;
- production behavior, schema, migrations, provider routing and publication behavior stay unchanged;
- operational checkout/database remain untouched.

Latest pre-remediation full-backend evidence on PR #370 was `1550 passed / 2 failed`; both remaining
failures are already tracked in #368 and are ambient Serper-fixture tests.

Tracking: #368 / PR #371. Founder remains the only PR merge authority.

## Read first and verify the actual ref

Read `AGENTS.md`, this file, `docs/TASKS.md`, `docs/CHECKLIST.md`, the canonical plan and the exact assigned task. Inspect local changes before fetching/synchronizing. Never reset, stash, clean, overwrite `.env`, or switch an active runtime to another checkout automatically.

Live GitHub refs/PR state/CI decide repository status. Local state requires dated Agent Local evidence; a merge is not deployment. Recheck the live branch before acting on the observations below.

## Fixed collaboration

- MG / ChatGPT: architecture -> code + regression tests -> self-review -> run/triage OpenCodeReview as the only supplementary semantic reviewer -> fixes -> prepare exact candidate SHA/PR -> review Agent Local evidence -> decide technical merge readiness. Do not invoke GitHub Codex review/security-review automation.
- Founder: product/editorial decisions, authorization of sensitive real executions, dispatch of local tasks, and PR merge.
- Agent Local: sync exact SHA -> run heavy verification on the real machine (focused/full tests, disposable DB/migrations, runtime/smoke, frontend build, exact-ref OCR when local execution is required) -> return normalized evidence. Code edits only when Founder/MG dispatches an explicit bounded coding scope.
- GitHub Actions: minimum confirmation gate only; do not duplicate the full Agent Local suite. If quota/service is unavailable, record CI as unavailable and use the exact-SHA Agent Local proof + MG review path.
- GitHub: shared code/contracts/plans/tasks/evidence, not a direct communication channel to Agent Local.
- Product naming: on macOS the desktop application is **ChatGPT** (OpenAI renamed the former Codex app surface). Keep technical/runtime identifiers and the packaged CLI executable such as `codex_cli` / `/Applications/ChatGPT.app/Contents/Resources/codex` unchanged unless the actual technical contract changes.

A GitHub comment or roadmap does not dispatch a local task. Never claim fresh local agreement without a returned report. Canonical merge flow is `MG code/tests/self-review -> OpenCodeReview supplementary review -> Agent Local exact-SHA heavy verification -> MG evidence review -> minimal GitHub CI when available -> Founder merge`. Do not create/comment GitHub Codex review or security-review triggers. During Actions quota/service outage, omit only the GitHub CI step and disclose that fact. WIP: one implementation plus related verification.

## Current delivery state

Live GitHub main for the current Question Map track: `99385a36cd0ef4e414fd1404c3e8aee4117b4d1f` (merge PR #370 / QM-02E Founder UI). Older delivery-track SHAs below are historical context, not the current repository ref. CQ-01 through CQ-06 are merged. PR #269 is merged and Coverage Support failure diagnostics survive rollback. CQ-07 Attempt 7 failed safely with `insufficient_evidence`; issue #270 remains the reusable approved EvidenceSet remediation. P1 DATA-02 / PR #274, RUN-02 MIN / PR #276 and REC-02 / PR #279 are complete. LOCAL-E2E-01 / PR #280 then retried once on the preserved disposable lineage after Founder authorization: the worker failed safely before Angle with `insufficient_support`, zero ModelCall/ToolCall, no new case, no second retry and no operational/publication mutation. PR #284 now ports the approved locked EvidenceSet reuse path onto current main; old PR #271 is stale/non-mergeable and is superseded by #284. Code migration head is `20260926_0044`; the latest verified operational DB revision is also `20260926_0044`. No further #280 retry, operational migration, publication or Attempt 8 is authorized.

| Phase | State | Meaning |
|---|---|---|
| F0 / UI-01 | DONE / acceptance PASS / PR #93 merged | Browser intake -> Start -> real Angle -> exact AngleApproval proved. |
| Planning / roles | DONE / PR #101 merged | Founder relay, MG ownership and finish-first policy established. |
| F1 | DONE / PR #102 merged | Canonical `operator_runtime` and safe next-action resolver. |
| F2 | DONE / acceptance PASS / PR #103 merged | Exact Outline path and OutlineApproval backend proof. |
| F3 | DONE / acceptance PASS / PR #104 merged | Independent canonical `vi-VN` / `en` Writer lanes. |
| F4 | DONE / acceptance PASS / PR #105 merged | Review/Revise -> Audit -> Source-copy -> exact final_content -> final_review gate. |
| F5 | DONE / `PASS_F5_FINALIZATION` | PR #109 + PR #113; #110 accepted exact VI/EN approvals -> ContentVersions -> `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED`. |
| F6-MINI | DONE / browser acceptance PASS | Browser workspace and canonical end-to-end browser acceptance are complete; #116/#118 and related P1 trackers are closed. |
| F6.A1 | DONE / real browser acceptance PASS | Exact fresh browser path reached `COMPLETE / APPROVED_NOT_PUBLISHED / NOT_PUBLISHED` with operational DB non-interference. |
| OCR-01 | DONE / PR #121 MERGED / Issue #119 CLOSED | OpenCodeReview Delegation Mode is advisory. Historical OCR-01 evidence remains tied to v1.12.5; the current routine exact-ref baseline is upstream v1.12.11, verified as the latest release on 2026-10-01. |
| P2 / O1 | DONE / O1.0-O1.4 PASS | Controlled operational release is complete: exact DB identity, backup/restore, migration to `20260915_0034`, lifecycle/restart proof, post-release preflight and fresh rev-0034 recovery proof all PASS with publication locked. |
| P1 / DATA-02 | DONE / PR #274 merged | Fresh backup, isolated restore and disposable `0034 -> 0044` rehearsal passed without operational mutation. |
| P1 / RUN-02 MIN | DONE / PR #276 merged | Disposable 0044 backend/frontend readiness, one-shot worker and graceful event/exit-driven shutdown proved. |
| P1 / REC-02 | DONE / PR #279 merged / `PASS_P1_REC02` | Crash/restart, stale-worker rejection, idempotency and reconcile-before-resend proved on disposable state. |
| P1 / LOCAL-E2E-01 | BLOCKED / PR #280 draft | One Founder-authorized retry + one one-shot worker ran on the preserved lineage and stopped before Angle on `insufficient_support`; zero ModelCall/ToolCall, no second retry. |
| F7 | LEGACY PAUSED / audit-only lineage | Historical R4 reached `AWAITING_APPROVAL / outline` and later read-only closeout passed. This lineage is not current Content Quality WIP and must not be resumed merely to advance CQ-02. |
| F8 | PLANNED | Evidence-led polish and CE05 closeout. |

Code migration head is `20260926_0044`; the latest verified operational database/source is `20260926_0044`. Historical O1.3/O1.4 release/recovery evidence below remains valid for its original rev-0034 checkpoints; later controlled migration/verification advanced the operational source to 0044. Backend/frontend/worker were stopped after the latest proofs.

Separate non-core publication track:
- #114 Editorial Quality Pass: produce a successor publication-ready revision without mutating accepted V1.
- #115 Publish Approval Gate: keep final-review approval distinct from permission to publish.
Neither authorizes publication.

## Immediate task

Close #368 / PR #371 on one exact candidate SHA, then clean merged #370 local/remote residue.

Required proof:
- exact Base -> Candidate diff hygiene;
- Ruff + mypy PASS;
- all five original #368 tests PASS;
- affected tests pass with ambient provider secrets absent and with synthetic provider secrets present;
- full backend passes from a freshly reset `contentengine_test`;
- no operational DB/schema mutation;
- exact-ref OCR + minimal GitHub CI + Agent Local exact-SHA verification + MG final review;
- after verification, remove only stale #370 disposable worktrees/feature refs;
- retain the fresh O1.1 backup pair for #361;
- do not move the operational checkout from its verified pinned HEAD.

Do not begin #361 Golden E2E until #368 is clean and PR #371 is merged.

## Pilot operating priority — 2026-10-03

Near-term goal: produce a small batch of real content that Founder accepts, then repeat it on one stable release. Engineering work must remove a demonstrated blocker to that outcome.

Critical path:
1. Complete PR #284, the current-main approved locked EvidenceSet reuse path. The LOCAL-E2E #280 retry proved this is now the concrete blocker.
2. Prepare a human-reviewed EvidenceSet for the exact preserved #280 ContentCase through the valid evidence/approval/lock workflow; do not direct-edit workflow state.
3. After #284 is merged and that EvidenceSet exists, Founder may separately decide whether one more #280 retry is justified. Until then, #280 remains BLOCKED.
4. Only after P1 proof, request the separate Founder authorization for operational migration/pilot storage. Disposable DB remains verification-only.
5. Run the frozen P01 + C02 pair as the first editorial pilot on one stable release. Record Founder edits, usefulness, overlap and final VI/EN evidence.
6. Run 2-3 additional real articles on the same release. Improve only recurring or blocking defects demonstrated by these runs.

Deprioritized until evidence shows a need: broad dashboard/UI polish, WordPress/Rank Math activation, auto-publish, new framework/provider work and wider automation. PR #282 Antigravity is not part of the critical path unless the current account/model route remains unusable after an explicit capability decision.

## Current working log

- 2026-09-20: PR #160 and #161 were already merged; #158/#159 closed.
- 2026-09-20: Fresh F7.2A-R4 ran on exact main `39336052e18b1761e3a63c73f746aab7d91eaa85`; truthful packaged CLI was `codex-cli 0.155.0-alpha.9.2` at `/Applications/ChatGPT.app/Contents/Resources/codex`.
- 2026-09-20: R4 produced locked factual evidence and reached the Angle gate. Founder manually selected `angle-environment-checklist`.
- 2026-09-20: Agent Local then submitted one Continue and normal Outline generation reached `AWAITING_APPROVAL / outline`; artifact `f671fa9d-3ab8-4ccd-abfc-beb3581f8077` v1 hash `eb48b9e08969d71c4a4bdc23cd4c61ae68ccbfa0b02888c748d5a45c311894ad`. No OutlineApproval/Writer/Quality/publication followed.
- 2026-09-20: formal #165 execution discipline was imperfect: the run used pre-#162 SHA and did not report a fresh slice-level `make release-preflight`. GitHub proved #162 changed docs only, so the already-created Outline was preserved and only read-only exact-main closeout was requested.
- 2026-09-20: Agent Local returned `PASS_F7_2B_READONLY_CLOSEOUT` on exact main `ed7e76ced561886940c1add77a85bf350c3f9ca5`: preflight PASS, durable Outline artifact/state unchanged, exactly one AngleApproval/Continue/Outline step/job/model call, zero OutlineApproval/Writer/Quality/ContentVersion/publication delta, and zero mutation during closeout.
- 2026-09-20: EvidenceSet bookkeeping corrected to 8 total rows = 6 institutional `supports` + 2 educational `context_only`; the previous `8 supports` wording was a reporting error.
- 2026-09-20: #167 opened because the historical Outline ModelCall metadata lacks `runner_executable` even though the actual runtime used `/Applications/ChatGPT.app/Contents/Resources/codex`. PR #166 now carries the bounded persistence fix + regression test; historical ModelCall is not mutated/backfilled.
- 2026-09-20: #164 was a false alarm caused by missing context about the Founder click; classify as no code/UI defect.
- Open audit bookkeeping: the R4 report states 8 supporting evidence items but enumerates 7; reconcile the missing eighth item in the next evidence review, but this does not negate the already-proven factual threshold because at least 7 authoritative supports were explicitly enumerated.

- 2026-09-30: PR #239 merged; pre-CQ07 test isolation and simplified safe local-run README are on main.
- 2026-09-30: Issue #240 read-only audit passed for exact packaged `codex-cli 0.159.0`, SHA-256 `ccd1b9441d35ce30102059c78514a125d676e6765ea1d001033e8cbe88718314`.
- 2026-09-30: PR #241 merged; exact Codex 0.159.0 repin is on main `6bb7a2fa16383a685daf5c84490eface1c91071e`.
- 2026-09-30: Agent Local returned `PASS_CQ07_FRESH_BASELINE_READY` on a fresh disposable DB `contentengine_cq07_baseline_20260930_test`, rev `20260926_0044`, preflight READY, zero model/provider calls. Historical PR #238 is not an execution branch and must not be widened or merged as a bundle.
- 2026-10-01: PR #252 capability-based Codex compatibility, PR #255 coverage-aware research query/support semantics, and PR #257 checkout-rooted Alembic preflight are merged.
- 2026-10-01: P01-R2 Attempt 5 passed post-#257 readiness, then failed before ModelCall with `insufficient_evidence`; diagnostic proved 3 selected discovery-only sources, 2 successful Jina reads and one bounded `http_409`.
- 2026-10-01: MG reclassified the root cause as evidence-source selection/acquisition because discovery-only sources cannot become automatic factual `SUPPORTS`; #263 / PR #264 is the bounded remediation.
- 2026-10-01: Agent Local exact-SHA verification of PR #264 passed 1290 backend tests, focused authority/second-hop suites, Ruff, mypy and OCR v1.12.11; GitHub CI #2067 PASS. Codex review requested canonical state updates in the same PR before merge readiness.
- 2026-10-01: Founder merged PR #264 as main `9a57b4ed39404081ff4ef8ab8942ba029ce9da35`; post-merge readiness passed and Founder authorized exactly one Attempt 6.
- 2026-10-01: Attempt 6 ran exactly once and failed safely at Coverage Support with only `coverage-5` unresolved; no Attempt 7, no queued/leased work, no Angle artifact and operational DB unchanged.
- 2026-10-01: Read-only diagnosis exposed an observability gap: the generated EvidenceSet/Evidence/SourceDocument rows roll back on failed Start-to-Angle, while the persisted Coverage Support diagnostic did not retain the bounded evidence/research/full-assessment snapshot needed to classify the remaining gap. #268 is the active fix.
- 2026-10-01: PR #269 R5 exact-head local verification passed focused/full backend, Ruff, mypy, OpenAPI and OCR, but later Codex review findings on the same production delta remained valid: robust URL redaction/malformed-URL tolerance, legacy oversized intake replay, and pre-research aggregate size fail-fast. MG fixed those findings on the same PR; a new exact-head closeout is required before merge readiness.
- 2026-10-02: Agent Local R6 exact-head verification passed on `b4560d7b2bbbf0e89744a57f4f5b726a092203d3`, but the subsequent Codex review found one additional valid P2: the pre-research 64KB check reserved no bytes for the up-to-8 automatic Evidence items. MG fixed this by sharing the automatic claim/count limits with Research and reserving a worst-case Evidence payload before any external research. R7 exact-head verification is required; Attempt 7 remains unauthorized.
- 2026-10-02: Agent Local R8 exact-head verification passed on `3027875c613ca3cc6cc55db5e947587fb2e70517`, and CI #2105 passed, but the subsequent Codex review found one valid P2 URL-redaction edge case: an authority-less value such as `https:user:SECRET@example.test/path` parses without `netloc` and could leak credential-like path text into the durable diagnostic. MG now fingerprints any non-authority or non-HTTP(S) diagnostic URL instead of persisting its path. A new exact-head closeout is required; Attempt 7 remains unauthorized.
- 2026-10-02: Agent Local R9 exact-head verification passed on `e05d6a8e03aff0bacabd733b23c05712f94eda43`, CI #2110 passed, and Security Review reported no findings, but Codex Code Review found one valid P1: path-carried session credentials such as `;jsessionid=...` could still survive because valid HTTP(S) paths were persisted verbatim. MG changed diagnostic URLs to preserve only sanitized origin plus a path SHA-256 fingerprint; raw path/query/fragment/userinfo are no longer durable. R10 exact-head closeout is required; Attempt 7 remains unauthorized.
- 2026-10-02: Agent Local R11 exact-head verification passed on `27144d67e90fa3fc08ebf3014b4c4eba339a8108` with 1300 backend tests, Ruff/mypy/OpenAPI and OCR clean, but the subsequent Codex review found one valid P2: automatic claim text containing C0 controls can expand to six JSON bytes per code point, exceeding the four-byte UTF-8 reserve used by the pre-research capacity check. MG added a shared canonical-JSON byte contract for automatic claims; extraction now rejects any claim/excerpt whose canonical JSON string exceeds the reserved width. R12 exact-head closeout is required; Attempt 7 remains unauthorized.
- 2026-10-02: Agent Local R13 on `5a2b892b31499496aaaced2fa1c849d16b0c53d9` passed all functional/static/OCR gates but correctly blocked on base→head `git diff --check` due to one blank line at EOF. MG removed that whitespace and, during GitHub review closeout, also addressed an unresolved valid P1 from the prior Codex review: percent-encoded credential-like authority text could be parsed as a hostname and persisted. Diagnostic hostnames are now validated/normalized (IP or IDNA/DNS labels) and suspicious encoded authorities are fingerprinted. A new exact-head closeout is required; Attempt 7 remains unauthorized.
- 2026-10-02: Reverse review simplified the URL-safety design further: durable diagnostics no longer retain any provider-controlled URL component at all. Every non-empty URL is now represented only as `url-sha256:<full-sha256>`; this preserves stable correlation while eliminating query/userinfo/path/authority secret classes and the need for URL-parser edge-case logic. Verification workflow is MG-led: MG architecture/code/test/self-review first, CI and Codex/OpenCodeReview are supporting evidence, then Founder dispatches one final exact-SHA Agent Local proof; Founder alone merges.
- 2026-10-02: PR #269 merged as `639401d5c4f767e42ea131a8935abc040f7c14c3`; Attempt 7 subsequently failed safely with `insufficient_evidence`, leading to issue #270 / PR #271 for reuse of a human-reviewed approved locked EvidenceSet. Attempt 8 remains unauthorized.
- 2026-10-02: DATA-02 / PR #274 and RUN-02 MIN / PR #276 were already merged; REC-02 / PR #279 then merged as current main `c6e616104abedd3432dde84e837567ac8b5ea7d3`, completing the recovery/idempotency/reconciliation slice.
- 2026-10-02: LOCAL-E2E-01 / PR #280 exact-head verification passed Ruff/mypy/focused/full backend/frontend/OCR. The real disposable run reached research + Coverage Support and then failed closed because the connected Codex workspace was out of credits. The exact disposable case/run lineage is preserved and no code fix is justified for this blocker.
- 2026-10-03: Founder reset the near-term product goal to a real Founder-approved batch and repeatability. Current pilot order is #284 -> exact approved+locked EvidenceSet for the preserved #280 ContentCase -> separately authorized #280 retry -> operational pilot storage -> P01+C02 -> 2-3 more same-release articles. New implementation work requires a demonstrated blocker.
- 2026-10-03: Founder authorized exactly one retry on preserved LOCAL-E2E-01 lineage and then exactly one one-shot worker. Retry command `1a8e1332-51e2-494e-a713-80b1e04365aa` created job `f6645b4e-de2e-4a55-9d77-bf1e50d5321c`; worker attempt 2 failed safely on `operator_worker_coverage_support_unresolved / insufficient_support`. Diagnostic artifact `3aa059ed-52a5-4e8e-b97a-f0aed7b54de8`, hash `c70e7569e42efcf23a66a08d16d659f52bca26aa24d080bb62f065b105639d6b`. Zero ModelCall/ToolCall; operational source remained rev-0034 and unchanged. No second retry authorized.
- 2026-10-03: Because #280 now proves an evidence-sufficiency blocker, stale PR #271 was superseded by PR #284, a clean port of the approved locked EvidenceSet reuse implementation onto current main `857b536823d8514c42da714d20e4e9ed1f5845a2`.
- 2026-10-03: Agent Local stopped PR #284 at the first focused-test blocker: the negative fixture attempted an impossible direct locked EvidenceSet insert, violating the existing initial-draft DB guard. MG replaced that fixture with a schema-valid generic-approved+locked snapshot that intentionally lacks the stronger reuse snapshot binding. Codex then reported a valid P1: EvidenceSet approval previously bound only member IDs, so nested Evidence/Claim/SourceDocument mutation could change approved facts. MG added an immutable approval-reason snapshot marker that hashes the complete reusable factual/provenance snapshot, plus a regression that mutates nested document/evidence content consistently after approval and requires fail-closed mismatch. No schema migration was added.
- 2026-10-03: Founder changed the review process: from this point forward MG must not invoke GitHub Codex review or security-review comments. OpenCodeReview is the only supplementary semantic reviewer; Agent Local exact-SHA verification, MG evidence review, minimum CI when available and Founder-only merge remain unchanged. Earlier Codex review records are retained as historical evidence only.
- 2026-10-03: OpenCodeReview Delegation Mode on PR #284 exact ref `69d79140583d99b2143b4d0619aac2a2e4a9dd1d` returned two valid P1 findings and two valid P2 docs findings. MG fixed stale locked-version selection, nested snapshot race protection, current-main docs and the stale `#271` pilot-order reference. A later OCR pass on `131b77eb16c9cf43a57e8aebc7cdf97f55727df2` found one valid P1 in that remediation: when the latest EvidenceSet is draft/review, reuse must not fall back to an older locked version, but it also must not block the canonical automatic-research path. The loader now returns no reusable snapshot in that state, so Start-to-Angle proceeds through fresh research; malformed latest locked snapshots still fail closed.
- 2026-10-03: OpenCodeReview on `10ce63ddbe374ac0a6be3fbd9ab421df3aea0d23` found a valid P1 in the exact approval read: the approval query did not force ORM refresh or row locking. The approval table is already DB-immutable (`evidence_set_approval_is_immutable` blocks raw UPDATE/DELETE), so concurrent mutation risk is narrower than the finding wording, but stale identity-map reuse remained possible. PR #284 now reads the exact approval with `populate_existing=True` + `FOR UPDATE`; the regression gate asserts both refresh execution options and a row-locking SELECT for `evidence_set_approvals` before reuse.
- 2026-10-03: OpenCodeReview on `6ce15e5b25dd8e849b1248fb74a274f7c0b20eb1` found a valid production-wiring P1: the reusable snapshot approval helper was only exercised directly by tests, while the historical operational path still used generic `approve_evidence_set()` through one-off Python. PR #284 now adds the canonical zero-provider `scripts.approve_reusable_evidence_set` production CLI, exposes curated EvidenceSet `content_hash`, and proves the command can create the exact marker-bound approval that `lock_evidence_set` and the reuse loader consume. Current manual production sequence is reviewed evidence -> curate exact EvidenceSet -> reusable approval command -> exact lock.

## Remaining order and completion meaning

Canonical plan: `docs/logs/2026-09-16-finish-first-delivery-plan.md`.

`F3 Writers -> F4 quality/final gate -> F5 canonical finalization -> F6-MINI implementation -> F6.A1 browser acceptance -> O1 operational release proof -> F7 two additional real cases -> F8 evidence-led polish/closeout`

- After F5 acceptance: backend normal-path functionality is complete, NOT the entire operational product.
- After F6.A1 + O1: the browser path is ready for a controlled operational pilot. This condition is now met.
- After F7 + release-blocker closure: decide CE05 V1 closeout from evidence, not PR count.

F6 has three bounded parts: app shell/status, full case workspace, dense Production Board. Backend/read-model contracts for these are checked during F3-F5; broad visual work follows backend completion. Basic usable errors, keyboard/focus, stale-state protection and recovery are pre-pilot requirements, not optional polish.

## Guardrails

Reuse existing services; no new workflow engine or broad F1 refactor. Keep backend authority and three human content gates. Frontend never chooses internal stage/provider/model/prompt/recipe/worker. Exact approved content and evidence/context bindings remain mandatory. Preserve all surviving warnings.

Recovery, idempotency and wrong-version approval tests ship with each affected stage. An ambiguous external outcome must be reconciled before retry; never promise blanket exactly-once model execution. Security, data-loss and approval-bypass defects block immediately, even on first occurrence.

UI displays only canonical data. Health can be unknown/stale; installed CLI is not worker liveness. `Approved / Not published` is distinct from publishing. No invented due dates, percentages, accounts or activity.

OpenCodeReview is a second semantic reviewer, not workflow authority or runtime proof. For routine OCR use, use upstream v1.12.11 (latest verified release on 2026-10-01), Git >=2.41, exact full commit SHAs, tests/operational config in review scope, and classify every finding before code changes. Historical evidence keeps the OCR version actually used; do not rewrite old v1.12.5/v1.12.6/v1.12.9 proofs.

Operational migration requires explicit authorization, backup/restore proof and frozen-M1 verification. New Model Routing policy activation is optional for V1 when existing approved routes suffice. No WordPress/publish, Artwork expansion, vector DB, native Codex multi-agent or Antigravity production activation in this completion scope.

## Approved next architecture direction — 2026-09-21

Founder approved `docs/21-CUSTOMER-LIVING-MAP-AUTOPILOT-SPEC.md` as the next product architecture track.

Target flow:

```text
Deep Research
→ Raw Sources
→ Signal
→ Customer Insight
→ Customer Living Map (Audience + Needs + Journey)
→ Content Coverage
→ Content Opportunity
→ Lens Selection
→ Evidence / Originality
→ Angle → Outline → Writer
→ Reader Value → SEO/AI Readiness
→ Publish
→ Search / Behaviour / Sales
→ Signal
→ Customer Map Update
```

Automation goal: about 99% of execution through controlled plans, least-privilege capabilities, existing Harness, independent review and human-by-exception.

This docs change does NOT:
- authorize local migration;
- authorize a paid/model run;
- activate Antigravity;
- remove Angle/Outline/final approvals;
- authorize publication;
- mutate the active F7 runtime lineage.

After ARCH-21 merge, first code slice is CT-01 CustomerInsight foundation, followed by AU-01 ExecutionPlan + capability policy.

## AU-01 implementation window — 2026-09-21

Live main at AU-01 start: `e17784d92f1a56277d52b3b9323d778973ea2602`, merge commit of PR #172.

CT-01 is complete at code/review level. Operational DB remains at the previously verified rev-0034 until a separate Founder-authorized migration task; AU-01 does not consume that authorization.

Current bounded implementation:
- branch `feat/au01-execution-plan-policy`;
- immutable ExecutionPlan Artifact bound to exact run/step/SettingsSnapshot;
- capability policy stored in existing versioned SettingsSnapshot;
- canonical semantic action namespaces mapped to capabilities;
- fail-closed tool/action/capability/budget/timeout/attempt checks;
- human-gate declaration required for publish/settings/prompt/workflow-changing capabilities;
- reuses the existing DB immutability guards for SettingsSnapshot and all Artifacts; no AU-01 migration is added;
- no second workflow engine;
- no Agent Bridge/auto-next execution yet — that remains AU-02.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local bounded proof → Founder merge`.

## CM-01 implementation window — 2026-09-21

PR #173 is merged. Live main at CM-01 start is `13485b0e28c0881c7a68a888e86e016c008241bc`.

AU-01 is DONE at code/review level. It added no migration. Operational DB remains under the existing controlled-release state; neither CT-01 rev-0035 nor CM-01 rev-0036 is authorized for operational application by this implementation work.

Current bounded implementation:
- branch `feat/cm01-customer-living-map`;
- PR #174;
- project-level Customer Living Map from AudienceHypothesis + NeedHypothesis + latest CustomerInsight;
- explicit immutable/audited CustomerInsight ↔ NeedHypothesis relation with project/audience guards;
- Journey remains a configurable derived view, not a persisted Need↔Journey truth table;
- deterministic run-bound `customer_map_snapshot` Artifact;
- incremental NEW / SUPPORT / CONTRADICT / DUPLICATE report;
- read-only summary/audience/changes APIs;
- read/refresh path does not invoke research, models, tools or delegated workers;
- Content Coverage, Lens Selection and UI are not part of CM-01.

CM-01 code migration head is `20260921_0036`. Any operational migration remains a separate Founder-authorized task with the existing backup/restore/rehearsal discipline.

Review flow:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local disposable-DB proof → Founder merge`.

## CC-01 implementation window — 2026-09-21

PR #174 is merged. Live main at CC-01 start is `e8fd9221099eea458051d53ab51cfc5a0cf57d41`.

CM-01 is DONE at code/review level. Operational DB remains at the separately controlled release state; rev-0035, rev-0036 and new CC-01 rev-0037 are not authorized for operational application by this implementation work.

Current bounded implementation:
- branch `feat/cc01-content-coverage`;
- reuse existing `ContentCase.need_hypothesis_id` as primary Need and block silent reassignment;
- add immutable/audited supporting Need links;
- add immutable/audited ContentItem ↔ Journey-stage links;
- deterministic project/locale/audience/need Content Coverage read model;
- coverage states `MISSING / PLANNED / IN_PROGRESS / PUBLISHED / NEEDS_UPDATE / WEAK / INSUFFICIENT_DATA`;
- no `WORKING` claim until PM-01 measurement evidence exists;
- duplicate candidates require same primary Need + locale + intent + normalized primary question;
- selected ContentOpportunity target refs are reused for update/refresh detection;
- locale-filtered coverage only counts matching LocaleVariants;
- planning inconsistencies do not erase already-known published coverage;
- read-only `GET /content-coverage`;
- no research/model/tool/delegated-worker execution in the read path;
- Content Opportunity generation, Lens Selection and measurement are not part of CC-01.

CC-01 code migration head is `20260921_0037`. Any operational migration remains a separate Founder-authorized task with backup/restore/rehearsal discipline.

Review flow:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local disposable-DB proof → Founder merge`.

## LS-01 implementation window — 2026-09-21

PR #175 is merged. Live main at LS-01 start is `5249ad08ad4c50f8cec91f72a23224170b071b26`.

CC-01 is DONE at code/review level. Operational DB remains at the separately controlled rev-0034 release; rev-0035 → rev-0037 are not authorized operational migrations by this work.

Current bounded LS-01 implementation:
- branch `feat/ls01-lens-selection`;
- no new DB migration; code migration head remains rev-0037;
- exactly seven deterministic Lens candidates;
- exact inputs from selected ContentOpportunity + relevant Customer Map + locale-scoped Coverage + exact SettingsSnapshot;
- selected ContentOpportunity must match one durable HumanSelection;
- MISCONCEPTION requires an approved observed-belief ref; contradictory evidence alone is insufficient;
- versioned immutable `lens_candidates` and `lens_selection` Artifacts;
- reviewed SELECT/MERGE/HOLD/DROP contract with at most one primary Lens;
- no one-Lens-one-article behaviour;
- guard-critical missing evidence blocks SELECT/MERGE;
- approved SettingsVersion provenance for CASE/POV/causal guard authority;
- all-HOLD/DROP is a valid stop;
- selection output includes active + HOLD evidence requirements and angle_context;
- approved Lens authority content is carried explicitly downstream; opaque refs alone are not expected to make Angle infer a POV/case/causal statement;
- Lens Selection downstream reads reconstruct semantic payloads instead of trusting hash validity alone;
- StepRun-bound candidate/selection Artifacts are recorded in output refs; retries get distinct lineage;
- Angle receives Lens context only when a current valid active selection exists;
- no research/model/tool execution is introduced by Lens candidate/selection logic.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local proof → Founder merge`.

## AU-02 implementation window — 2026-09-21

PR #176 (LS-01) is merged. Live main at AU-02 start is `5f3cef586e74442e48e213b6229d697cbd34d103`.

Current bounded AU-02 implementation:
- branch `feat/au02-agent-bridge`;
- PR #177;
- no new DB migration; code Alembic head remains `20260921_0037`;
- reuses ContentRun / StepRun / Job / Approval / Artifact / checkpoint / DelegationExecution;
- no second workflow engine;
- exact AU-01 ExecutionPlan + SettingsSnapshot + task + worker binding;
- worker claim returns the exact authorized plan and settings identity;
- human-gated plans require the canonical approval-request checkpoint, exact approved Approval, canonical approval checkpoint, non-worker actor, and executable run state before queue/claim;
- approval is rechecked at execution operations, not accepted only as a plan declaration;
- worker-scoped claim/heartbeat/expiry reclaim with bounded attempts and absolute plan/budget deadline;
- durable ModelCall/ToolCall/output-token/cost/wall-clock budgets enforced; non-durable AU-01 counters fail closed instead of trusting worker self-reporting;
- completion validates exact output lineage/type/hash/latest version;
- completion/failure receipts plus checkpoints provide restart/recovery evidence;
- root/subagent telemetry reuses DelegationExecution and excludes prompt/raw payload/COT;
- completion creates an independent review request; worker cannot self-certify;
- review request/result are semantically rebuilt from canonical lineage before auto-next;
- auto-next only materializes the next pending StepRun after review; it does not enqueue future work without that step's own ExecutionPlan;
- retryable failure creates a new StepRun + new ExecutionPlan; human-gated retry requires fresh approval;
- malformed SettingsVersion-like capability-policy provenance fails closed;
- no unauthenticated public bridge endpoint and no Antigravity activation are introduced by AU-02.

Important limitation made explicit rather than hidden: the current Harness does not durably ledger context-estimate, research-source and revise-loop counters at this bridge boundary. AU-02 therefore rejects plans using those budget counters until a durable source exists; it does not accept local-agent self-report as enforcement truth.

Operational DB remains under the separately controlled release state. AU-02 adds no migration and does not authorize applying rev-0035 → rev-0037 operationally.

Review flow remains:
`CI → exact-ref OpenCodeReview → MG triage → Agent Local exact-head proof → Founder merge`.

AU-02 verification hardening:
- output timestamp is strict: Artifact `created_at` must be greater than `StepRun.started_at`, not equal;
- external-only output Artifacts fail closed until ContentEngine has a canonical external-object resolver/hash verifier; AU-02 does not treat an arbitrary stored hash as proof of external object integrity.

## QA-01 implementation window — 2026-09-22

PR #177 (AU-02) is merged. QA-01 starts from exact main `49f430f42b47fda1160bf27e096c7b6309d2e32f`.

Current bounded QA-01 implementation:
- branch `feat/qa01-reader-value-readiness`;
- PR #178 remains draft until exact-ref review/proof is complete;
- quality route is `Review/Revise → Assertion Audit → Source-copy → Reader Value → SEO/AI Readiness → existing Founder final_review`;
- Reader Value is the prerequisite hard route: FAIL blocks the lane and Search/AI is not enqueued;
- Search/AI readiness remains a separate discovery-hygiene evaluator and cannot override Reader Value;
- no aggregate numeric score is used for routing;
- Reader Value receives the exact revised draft plus target reader/problem, Reader Transformation, selected Angle and sanitized concrete OriginalityPack;
- readiness handoffs/evaluations bind exact draft, Source-copy, settings and, for Search/AI, exact Reader Value lineage;
- technical retry accounting is scoped to the exact readiness handoff rather than unrelated locale history;
- evaluation calls are audit-only: no research, tools or rewrite;
- UI shows Reader Value and SEO/AI separately and surfaces actionable WARN/FAIL findings;
- the existing Founder final-review gate and publication lock remain unchanged;
- rev `20260922_0038` only seeds the versioned QA prompt/recipe registry. Applying rev-0035→0038 to the operational DB is NOT authorized by this implementation work;
- no Antigravity activation, no second workflow engine and no publication.

QA-01 review flow:
`CI → exact-ref OpenCodeReview Delegation → MG triage → Agent Local bounded exact-head proof → Founder merge`.

Do not claim QA-01 DONE until final CI, OCR, local proof and Founder merge are all complete.

## PM-01 implementation window — 2026-09-22

QA-01 / PR #178 is merged. PM-01 starts from exact main:
`5b8600de381a43e4282c93ee06767cb2b93cc62c`.

Current bounded PM-01 implementation:
- branch `feat/pm01-publish-measurement-identity`;
- rev `20260922_0039` adds durable publication + measurement identity; this does NOT authorize operational migration;
- reuse existing Harness Outbox/reconciliation primitives; no second side-effect/workflow engine;
- final editorial approval creates the approved ContentVersion, but DOES NOT authorize external publication;
- immutable Publish Package is built only from exact approved ContentVersion + canonical final approval history + non-failing QA-01 lineage + explicit ContentExperiment;
- a second `WAIT_HUMAN(publish_authorization)` Founder decision is required before any WordPress dispatch;
- WordPress handoff uses deterministic idempotency + existing OutboxIntent;
- commit-before-side-effect boundary is explicit: Outbox `processing` state must be durable before external WordPress write;
- ambiguous external outcome becomes `needs_reconciliation`; reconcile before any resend;
- PublishedContent preserves one ContentItem ↔ WordPress identity while immutable PublishEvent records draft/publish/update history by exact ContentVersion + ContentExperiment;
- ContentVersion remains immutable after Founder approval; PM-01 does not mutate `approved → published` or create a duplicate publication-only ContentVersion. Canonical external publication state is PublishedContent/PublishEvent;
- Discovery reuses only an exact-contract experiment that is still PLANNED/PENDING and unbound; once a prior experiment is bound, a later content/version cycle gets a fresh candidate rather than reusing historical identity;
- review_window_start/end must be set explicitly with timezone-aware datetimes and end > start before Publish Package; PM-01 does not infer a 7/14/30-day default;
- after all package inputs validate, ContentExperiment is frozen to the exact ContentItem/ContentVersion + measurement contract + review window; replacement candidates remain possible before external effect, but historical bindings are not rewritten;
- failed/conflicting persisted Discovery selection leaves the caller's in-memory OpportunityMap state unchanged;
- immediately before external dispatch, the package/experiment measurement snapshot is revalidated; stale state fails before Outbox moves to processing;
- Content Coverage + Review Console validate current PublishedContent against latest immutable PublishEvent and fail closed on mapping/history drift;
- core measurement rows normalize impressions/clicks/sessions/engaged sessions/artwork/visit/workshop transitions/inquiry while retaining aggregate/raw audit payload;
- measurement identity traces current external URL/version back to ContentCase, Audience, Need, Journey, Opportunity, Lens and ContentExperiment;
- metrics/observations remain observations; PM-01 does not create/promote LearningCandidate rules;
- no WordPress credential/network activation is performed by this GitHub-side implementation;
- no Search Console/Analytics credential activation is performed here;
- no Antigravity activation and no publication against a real site.

Operational database remains at the separately controlled release state. PM-01 does NOT authorize rev-0035 → rev-0039 operationally.

PM-01 implementation proof before final docs sync:
- CI #1518 PASS on `e2b75b6c288a5b85abd117d9b2cab42903a9b82d`;
- Ruff PASS;
- mypy PASS on 158 source files;
- rev-0038↔0039 migration round-trip PASS;
- backend 980 passed / 12 warnings;
- OpenAPI + frontend lint/typecheck/build PASS.

PM-01 still remains IN IMPLEMENTATION until exact final docs-head CI, exact-ref OpenCodeReview, Agent Local disposable proof and Founder merge.

PM-01 review flow remains:
`CI → exact-ref OpenCodeReview Delegation → MG triage → Agent Local disposable exact-head proof → Founder merge`.

## E2E-01 P2C2 Rank Math bridge window — 2026-09-24

P2C2.0 audit is accepted. P2C2.1 merged via PR #212 and P2C2.2 merged via
PR #213 after real `motgu.test` bridge/gateway verification. The active bounded
implementation is P2C2.3: exact publication identity guard plus immutable Rank Math
inspection capture.

Frozen architecture:
- WordPress post ID is the primary external identity; canonical URL is a locator, not identity;
- bridge source is tracked under `wordpress/motgu-rank-math-bridge/`;
- only three initial Rank Math abilities are exposed: post SEO meta, post schema and post links;
- there is no arbitrary ability-name endpoint and no generic MCP executor in the ContentEngine path;
- HMAC auth uses a secret outside Git plus a dedicated internal WordPress service-user ID;
- the bridge revalidates live ability annotations and fails closed on readonly/destructive/idempotency drift;
- output is allowlisted/bounded and must not expose secrets or raw settings;
- Search Console/GA metrics retain Google provenance and are not duplicated as Rank Math metrics;
- P2C2.1 does not publish, mutate WordPress, change Rank Math settings, persist ContentEngine Artifacts or activate `motgu.com`.

P2C2.2 adds only transport/config/parser behavior: HMAC SecretStr config, three
fixed GET methods, HTTPS except loopback dev, bounded timeout, redirects disabled, no
automatic retries, strict envelope/safe-data validation and stable fail-closed errors.
It does not yet bind a Rank Math read to PublishedContent/PublishEvent/ContentVersion or
persist an Artifact. During reverse-risk review, the bridge response was additionally
hardened with `Cache-Control: no-store, private` so authenticated SEO/draft metadata is
not cacheable merely because the custom HMAC request is not a normal logged-in WP REST
session.

P2C2.3 requires the requested ContentVersion to be the current PublishedContent version,
requires a matching immutable PublishEvent whose canonical URL/status/revision/publication
timestamp still matches the mapping, and revalidates the publish-package Artifact/run
lineage before any Rank Math state can be persisted. The validated inspection is stored
only as an immutable Harness Artifact owned by that publish run; there is no new
Rank Math table or migration.

Capture replay uses a deterministic snapshot fingerprint over publication identity,
Rank Math versions/capability and safe data while excluding capture time. An identical
snapshot reuses the existing Artifact; changed safe state creates the next immutable
Artifact version. Historical ContentVersion reads are permitted only when an exact
snapshot Artifact was already captured for that historical publish lineage. Missing
historical snapshots fail closed rather than reading current Rank Math state.

Next bounded gate after P2C2.3 is local exact-ref verification (P2C2.4), then separately
authorized production-readiness validation (P2C2.5).

## Historical E2E-01 activation unblock snapshot — 2026-09-25

Accepted readiness state:
- P2C2 local engineering/capture path through PR #214: DONE;
- A1 migration/recovery rehearsal PASS on the current rev-0034 recovery point;
- A2 production WordPress inventory BLOCKED because no authorized production admin/SSH/WP-CLI path is available;
- A3 secret-delivery design PASS, production provisioning still pending production access;
- A4E1 / PR #218 current 0034→0042 migration tooling: DONE with disposable proof;
- A4E2 / PR #220 current rev-0042 release lifecycle/build provenance: DONE with exact-ref local proof and merge-main CI PASS.

At the time of this readiness snapshot, the next E2E task would have been **A2 production WordPress inventory**. It is now PAUSED by the Founder while the Content Quality track is active; do not dispatch it from this historical section.

A4E1 adds a new current-generation operational migration entrypoint for exactly `20260915_0034 → 20260923_0042`. Historical `ops_migration_rehearsal.py` and `ops_operational_migrate.py` retain their 0027→0034 historical meaning. The new tool requires exact authorized clean code, stopped application runtime, format-v2 backup identity, explicit authorized dump SHA, exact source-documents fingerprint, exact migration chain, fail-closed pre/post schema guards and durable-state invariance. It never recreates/rebinds the Postgres container and must fail closed if the execution context cannot reach the exact operational DB.

The live operational DB is still rev-0034. The current Postgres container is healthy but has no host-published 5432 listener even though tracked compose declares loopback publishing; this topology drift is a separate execution-context concern and must not be silently “fixed” by migration code. Operational migration, release-runtime start, production WordPress changes, Rank Math bridge activation, production credentials and publication remain separately Founder-authorized.


## E2E-01 A4E2 closeout — 2026-09-25

Current main at A4E2 start: `383b274e57ced368dbbf0bc0216d45c8fb622ed9` (merge of PR #218 / A4E1).

A4E1 is complete at code/review/local-proof level. The production/operational ContentEngine database remains rev `20260915_0034`; applying the proven 0034→0042 migration remains a separate Founder-authorized operation.

A4E2 / #219 is complete via PR #220. The new `ops_release_lifecycle_0042.py` preserves historical `ops_release_lifecycle.py`, expects rev `20260923_0042`, requires exact clean checkout + local Python 3.12 venv + exact frontend build provenance, and uses event-driven process/log readiness with one-shot HTTP verification. It must not use repeated sleep/HTTP/ps/pgrep polling. Release provenance is local ignored evidence under `artifacts/release/`, not a committed generated artifact and contains no secrets.

Exact-ref local proof used an isolated disposable PostgreSQL restored from the accepted A1 recovery point and migrated to rev-0042 with the merged A4E1 tool; startup + restart + graceful shutdown passed with no durable/model/tool/outbox/publication delta. The operational DB/runtime remained untouched.

A4E2 exact-ref local proof initially stopped fail-closed on `agent_runner_version_not_approved` because the packaged Codex advanced from `.16.3` to `.16.4`. Issue #221 completed a read-only capability audit of exact binary SHA `93169e745735930598e867ad837abf3fdc50774a3ad7e7aa89c0d0c51b0189a5`: required runner flags, all 21 explicit no-tool controls and cached-session auth were preserved, with zero model/DB/runtime side effects. The audit authorized the exact repin to `codex-cli 0.155.0-alpha.16.4` only; ranges/wildcards remain forbidden. The repinned final PR #220 head passed CI and exact-ref local lifecycle proof.

A4E2D1 / #222 proved the two A1/live `running` Run/Step rows are intentional Start-to-Angle operator-retry pauses: latest Job is failed, no lease remains, failure evidence is persisted, and the only canonical operator action is an explicit retry that would resume research/model work. A4E2D2 / #223 narrowed only the rev-0042 release quiescence guard for that exact paused contract. Final proof preserved both paused lineages byte-for-byte while still blocking queued/leased jobs, active model/tool/outbox work, other stages/states, unmatched active Run/Step, multiple active Steps per Run, or failure-evidence mismatch. Historical rev-0034 lifecycle semantics remain unchanged.

## Historical E2E-01 resume order — preserved, currently PAUSED

If the Founder later resumes E2E-01, continue from this preserved order:
1. A2 production WordPress + Rank Math inventory — requires an already-authorized read-only production access path from Founder.
2. Production bridge secret/service-user provisioning after A2 validates the real host contract.
3. Founder-authorized operational migration `0034 → 0042`.
4. Founder-authorized exact operational rev-0042 release lifecycle.
5. A5 production edge/HMAC/cache/redirect preflight.
6. A6 final activation re-audit.
7. Only after `ACTIVATION_READY`: D1 freeze one new real E2E case, then D2-D9 closed-loop execution.

Do not substitute public HTTP guesses for A2. Do not migrate, start operational runtime, provision production credentials, mutate WordPress/Rank Math, publish, or run real Google/model work without the corresponding Founder authorization.

## Content Quality priority — CQ-01 through CQ-06 merged, CQ-07 active / P0

Founder priority remains CQ-07 closeout before P1 local production readiness or any production activation.

CQ sequence:
`CQ-01 Promise Coverage → CQ-02 Pillar/Cluster Contract → CQ-03 Evidence/Originality Depth → CQ-04 Angle/Outline Quality → CQ-05 Writer/Human Voice → CQ-06 Deep Quality Gate → CQ-07 real Pillar+Cluster pilot`.

CQ-01 merged:
- PR #226; promise coverage contract complete; historical no-coverage compatibility preserved.

CQ-02 merged:
- PR #228; canonical `pillar|cluster` contract complete; legacy `primary|NULL` readable; no invented durable relationship.

CQ-03 merged:
- PR #234; exact coverage support-depth blocks Angle on unresolved requirements with immutable/revalidated Evidence/Originality lineage.

CQ-04 merged:
- PR #235; merge/main `80ad589583d6d2b67e416109ccbd537a52139904`;
- exact verified implementation head `026ad2f57a3240218adfe4a03a66568e7442981d`;
- CI #36233164012 PASS;
- OCR v1.12.9: 18/18 reviewable, zero findings;
- Agent Local: 80 focused + 1226 full backend PASS; frontend PASS;
- Angle/Outline semantic gates now preserve exact lineage, role behavior and backward compatibility.

CQ-05 merged architecture:
- historical HV-01 / PR #186 is reference material only;
- do not add a second rewrite model stage by default;
- reuse existing Review/Revise as the Human Voice-aware bounded rewrite;
- source is one exact immutable locale Writer draft;
- rewritten output remains one immutable `journal_draft` with exact source/rewrite lineage;
- VI and EN remain independent and never consume sibling draft input;
- deterministic guards may detect introduced numeric/direct-quote drift, but are not a substitute for Assertion Audit;
- Human Voice may improve rhythm, specificity, warmth, lived texture and natural phrasing only within exact approved truth/support boundaries;
- no invented artist intent/quotes/customer stories/sensory observations/business promises/prices/scarcity/policies;
- every Human Voice rewrite must be re-audited against the new exact bytes before Source-copy/final quality advances;
- before/after diagnostics are explanatory, never AI-detector/authorship scores or a “humanization percentage”;
- no production activation, operational migration, publication or final-approval bypass in CQ-05.

- 2026-10-02: Founder reprioritized delivery to P1 and asked to temporarily ignore GitHub Codex Code Review. #272 opened as the P1 tracker and #273 as DATA-02. P0 is paused rather than closed; PR #271 remains open and Attempt 8 remains unauthorized. DATA-02 adds a current `0034 -> 0044` disposable migration rehearsal without widening historical O1 proof.

- 2026-10-02: DATA-02 merged via PR #274 as `65fc65c990d76ab1c6f164aa25bfab5d713cfada`. RUN-02 MIN / #275 is active and intentionally targets a disposable 0044 restore rather than migrating the operational 0034 DB. Runtime readiness uses child stdout events + one-shot HTTP checks + process exit, with an idle one-shot worker and no polling/sleep/ps/pgrep loops.

- 2026-10-02: RUN-02 MIN merged via PR #276 as `4dea3b478129e765fa088e7f4018277c3371a00d`. Technical proof passed on exact PR head `4e8b5d66ab49d91fb54a3c018a56b8a3dfce2385`. REC-02 / #277 is active on a stacked branch from that verified head; the merge commit introduced zero file delta, so the REC-02 branch contains only the recovery-proof delta relative to main.
