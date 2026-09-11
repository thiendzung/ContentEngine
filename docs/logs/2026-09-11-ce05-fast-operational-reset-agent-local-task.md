# CE05 — Fast Operational Reset — Agent Local Task

Date: 2026-09-11

## TASK ID

`CE05-FAST-OPERATIONAL-RESET-LOCAL`

## OWNER

Agent Local executes. MG reviews the final Operational Package V0. Founder gives final content/operational approval.

## OBJECTIVE

Get one fresh, safe, traceable MOTGU Journal candidate from the runtime database that is actually in use to a deterministic **Operational Package V0** in one bounded sprint.

Do not stop after successful intermediate gates. Finish first; harden after the first controlled operation.

The historical O4 UUIDs are NOT required if those rows are absent from the active runtime database.

## BASE

Execute only after the PR containing this task and `docs/logs/2026-09-11-ce05-fast-operational-reset.md` is merged.

Start from clean synchronized `main`.

```bash
git status --porcelain
```

Unexpected local changes => `BLOCKED`. Never auto reset/stash/delete/overwrite.

Then:

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse origin/main
git status --porcelain
```

Require HEAD == origin/main and clean.

## MUST READ

Only after synchronization:

1. `AGENTS.md`
2. `AI_context.MD`
3. `docs/TASKS.md`
4. `docs/CHECKLIST.md`
5. `docs/logs/2026-09-11-ce05-production-first-operating-mode.md`
6. `docs/logs/2026-09-11-ce05-fast-operational-reset.md`
7. current Journal modules/scripts needed for the exact path.

## FOUNDER-LOCKED PRODUCT DECISION

Reuse this decision without another intermediate human stop:

```text
Framing: How do I know if an original artwork is fairly priced?
Audience: first-time art buyer
Angle direction: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
```

Guardrails:

- no universal pricing formula;
- distinguish market/context facts from the buyer's personal decision;
- no investment/appreciation promise;
- no luxury/status framing;
- no artificial scarcity or pressure;
- no invented artist/work/business facts;
- live artwork-specific facts require current canonical MOTGU data and may be omitted if unavailable.

## OPERATING QUALITY POLICY

For this first controlled operational Journal, stop only on a **hard** blocker.

Hard blockers:

1. structural/schema/provenance/hash/lineage validation failure;
2. EvidenceSet cannot be reviewed, approved and locked from real readable evidence;
3. OriginalityPack cannot be approved from the exact Founder-authorized guardrails below;
4. Assertion Audit deterministic result is `fail` OR any critical unsupported/contradicted count is non-zero;
5. Source-copy has `fail_count > 0` under current v2 rules;
6. an unapproved provider/model/tool capability is required;
7. final visible VI or EN content is missing;
8. destructive/unbounded data mutation would be required;
9. a secret would need to be exposed.

Non-critical `warn` findings do NOT stop this first operational sprint. Preserve them exactly and surface them to Founder in the final package.

Do not change evaluator semantics or thresholds to obtain a pass.

## STEP 0 — RUNTIME / DATABASE RESOLUTION

Record:

- current main SHA;
- Python version;
- configured database name/host only (no password/secret);
- Alembic current/head;
- counts of Project, ContentCase, ContentRun, Artifact, QualityEvaluation.

### One cheap historical-lineage recovery probe

You may do exactly one read-only scan of locally accessible PostgreSQL non-template databases.

Do not expose connection strings or credentials. Do not edit `.env`.

Look only for the exact historical markers:

- ContentCase `9ec6133b-5f14-46d0-9866-e3b049e537b5`;
- EN v5 Artifact `4c17db56-e912-4097-92a0-d95f5d4fe565`;
- VI Source-copy Artifact `aa822f6f-c000-4008-a814-23e4d6a4caa2`.

If exactly one non-test database contains the complete markers AND its Alembic state is compatible with current main, use that database only through an ephemeral process environment override for this task. Do not copy records.

If none exists, or candidates are incomplete/ambiguous, immediately use the configured runtime database (`contentengine`) and continue fresh. **Do not block because historical UUIDs are absent.**

Report which path was selected: `REUSE_COMPLETE_RUNTIME_DB` or `FRESH_ACTIVE_DB`.

## STEP 1 — ENSURE RUNTIME BASELINE

Require current approved migration head. Apply only already-merged migrations if needed.

Require or create/reuse the `motgu` Project through existing safe application/model contracts. Do not create duplicate Project rows.

Verify current prompt/recipe/provider configuration required by the Journal path. Use the existing approved route where available; for model-backed CE05 Journal steps the expected route remains `codex_cli / gpt-5.6-luna`, no tools, unless current merged SettingsSnapshot/route contract explicitly resolves another already-approved route. Report the resolved route; never print credentials.

## STEP 2 — FRESH FOUNDER-SELECTED PLANNING SPINE IF NEEDED

If the selected runtime DB already contains a complete valid current Journal planning spine for the locked Founder question, reuse it.

Otherwise create a fresh planning spine for the exact Founder question.

### Preferred fast path

Prefer existing public persistence/service functions and existing model invariants to create/reuse exactly:

- NeedHypothesis: question / first-time art buyer / `PROPOSED`;
- ContentOpportunity: exact Founder question, decision `CREATE`, priority `NOW`, suggested content type `journal`;
- explicit Founder selection (`selected_by=founder`);
- corresponding planned ContentExperiment if the existing persistence contract creates/requires one.

This is an already-authorized Founder selection. Agent Local is not making a product choice.

A temporary local Python invocation from `backend/` may call existing public services/models for this bootstrap. It must not create a repository file or generic orchestration layer.

### Fallback only if the direct safe planning path is not practical

Run existing `scripts.run_discovery_research` once using the exact locked question/reader/situation, then persist a selection using the existing selection path.

If multiple `CREATE` + `journal` planning candidates exist, select deterministically by:

1. highest normalized token overlap between candidate question/title and the exact Founder question;
2. tie-break by planning opportunity identifier lexicographically.

Persist `selected_by=founder` and reason:

`Pre-authorized CE05 fast operational reset for the locked first-time-buyer pricing question.`

Do not stop for another opportunity-selection review.

Record the new/reused NeedHypothesis, ContentOpportunity, HumanSelection/selection metadata and ContentExperiment IDs.

## STEP 3 — BOUNDED REAL EVIDENCE

Use the existing Evidence Research workflow against the selected fresh opportunity/hypothesis.

First query is fixed:

```text
artwork appraisal fair market value condition provenance comparable sales (site:irs.gov OR site:si.edu)
```

Use current normal provider limits; maximum 4 pages and maximum 8 claims for this pass.

Human/read-only review inside this task must choose only evidence that:

- comes from successfully read SourceDocument content;
- has exact excerpt/locator support;
- directly helps explain artwork price/value context or appraisal limits;
- does not introduce investment promises or universal pricing formulas.

Target minimum for the curated set:

- >= 2 useful `supports` Evidence rows;
- >= 2 independent suitable source documents/domains;
- prefer `irs.gov`, `si.edu`, or equally strong institutional/government/academic sources.

If the first pass cannot satisfy this minimum, exactly ONE second bounded evidence pass is allowed, targeted only at the missing concept/domain. Do not broaden into generic web research.

If two passes still cannot produce the minimum real supports, STOP `BLOCKED_EVIDENCE_QUALITY`.

Curate a fresh EvidenceSet from the reviewed Evidence IDs using existing `scripts.curate_evidence_set` / service path.

Approve the exact draft snapshot through existing `approve_evidence_set()` with:

```text
approved_by = mg_content_engine
approval_reason = Approved for CE05 first operational Journal; reviewed real supports satisfy the fast operational evidence gate.
```

Then lock that exact approved EvidenceSet through the existing lock path. Do not mutate evidence membership after approval/lock.

Record IDs/version/hash/approval/lock metadata and selected Evidence excerpts/domains.

## STEP 4 — FRESH ORIGINALITY PACK

Create/reuse one OriginalityPack for the fresh ContentCase using existing `scripts.curate_originality_pack` / service path.

Use exactly these four Founder-authorized structured `motgu_owned_material` items. Preserve the meaning; compact wording is allowed only where required by current schema.

### ORIG-01

```json
{
  "type": "motgu_owned_material",
  "source_ref": "MOTGU-INPUT-ORIG-01",
  "material": "Specific artwork identity, dimensions, materials, current price, sale status and location are live physical-work facts and must come only from current canonical MOTGU data.",
  "writer_use": "Use as a guard for what the buyer should inspect; omit specific live facts when canonical current artwork data is not present.",
  "guardrails": "Never invent current artwork facts, artist facts, price, availability or location.",
  "approval_ref": "founder:ce05-fast-operational-reset:ORIG-01"
}
```

### ORIG-02

```json
{
  "type": "motgu_owned_material",
  "source_ref": "MOTGU-INPUT-ORIG-02",
  "material": "Packaging, shipping and insurance may be separate practical costs; oversize or special handling may require a quote.",
  "writer_use": "Help a first-time buyer separate artwork price from practical transaction costs.",
  "guardrails": "Do not invent shipping prices, insurance terms or logistics promises.",
  "approval_ref": "founder:ce05-fast-operational-reset:ORIG-02"
}
```

### ORIG-03

```json
{
  "type": "motgu_owned_material",
  "source_ref": "MOTGU-INPUT-ORIG-03",
  "material": "Sale status and physical location are separate facts and must not be turned into fake urgency or scarcity.",
  "writer_use": "Explain availability calmly when current canonical data exists.",
  "guardrails": "No artificial scarcity, countdowns, urgency or availability claims without canonical current data.",
  "approval_ref": "founder:ce05-fast-operational-reset:ORIG-03"
}
```

### ORIG-04

```json
{
  "type": "motgu_owned_material",
  "source_ref": "MOTGU-INPUT-ORIG-04",
  "material": "MOTGU's intended buying experience is calm, low-pressure and artwork-centered.",
  "writer_use": "Keep the Journal practical, reassuring and centered on understanding the work rather than status or speculation.",
  "guardrails": "No investment, appreciation, luxury-status or pressure framing.",
  "approval_ref": "founder:ce05-fast-operational-reset:ORIG-04"
}
```

Approve the exact pack through existing `approve_originality_pack()` using exact snapshot hash:

```text
approved_by = founder
approval_reason = Re-approved Founder guardrails for CE05 fresh operational acceptance on the active runtime database.
```

Require final pack status `approved`, valid snapshot hash, >= 1 usable material item (expected 4).

Do not stop for another Originality review.

## STEP 5 — JOURNAL RUN + INPUT BUNDLE

Create/reuse a fresh Journal ContentRun through the current merged harness lifecycle and current SettingsSnapshot contract.

Create the required research/input StepRun and build the immutable `journal_input_bundle` using existing `JournalResearchHandoff` methods:

- exact selected ContentOpportunity;
- exact locked EvidenceSet;
- exact approved OriginalityPack;
- `REUSE_EXISTING` after research has been completed outside the model-generation step;
- provider/model call counts required by that bundle contract.

Require exact hash/provenance validation.

Record ContentRun, StepRun, SettingsSnapshot and bundle ID/version/hash.

If a standalone CLI is missing, use a temporary local Python invocation that calls the merged public harness/Journal service functions. Do not add repo code merely for orchestration.

## STEP 6 — ANGLE GENERATION + PRE-AUTHORIZED SELECTION

Run the current merged Angle generation runtime using the approved no-tool model route and exact bundle.

Require 3–5 schema-valid candidates and persisted provenance.

Select one candidate without another human stop using this deterministic pre-authorized rule:

1. reject any candidate whose title/promise/POV introduces investment, appreciation, luxury, scarcity/urgency, or universal pricing-formula framing;
2. among remaining candidates, score normalized token overlap of `working_title` with:
   `A First-Time Buyer’s Checklist for Understanding an Artwork’s Price`;
3. highest score wins;
4. tie-break by `angle_id` lexical ascending.

Approve that exact candidate through the existing AngleApproval path with `approved_by=founder` and reason:

`Pre-authorized Founder checklist direction for CE05 fast operational acceptance.`

This is execution of the locked Founder decision, not a new Agent Local editorial decision.

Record Angle Artifact, candidate hash and AngleApproval.

## STEP 7 — OUTLINE → BILINGUAL WRITERS → REVIEW/REVISE

Continue without stopping:

1. Outline from the exact approved Angle;
2. VI writer;
3. EN writer;
4. Review/Revise for each locale using the current merged CE05 contracts.

Use existing scripts where available. If a script name contains `real_o4`, it may be used only if its CLI accepts the fresh IDs/hashes and does not hard-code the vanished historical UUIDs. Otherwise invoke the same merged public service functions temporarily from `backend/`; do not fork or duplicate the implementation.

Normal contract-defined validation retry/recovery is allowed. Do not create speculative content cleanup code.

Require final visible VI and EN draft artifacts and record exact IDs/versions/hashes.

If one locale has a non-critical content warning at an intermediate review gate, preserve it and continue unless the current hard contract itself prevents downstream execution. Do not weaken code to bypass a hard contract.

## STEP 8 — ASSERTION AUDIT VI + EN

Run current Assertion Audit on the final visible VI and EN drafts.

Hard requirement for each locale:

```text
audit_result != fail
critical_unsupported_count = 0
critical_contradicted_count = 0
```

If the evaluator reports non-critical warnings but the hard conditions above are clean, preserve the warnings and continue.

Run one exact rerun per locale only where the merged runtime supports normal idempotency; record whether reuse occurs. Do not turn an idempotency diagnostic issue into a blocker unless it creates ambiguous/corrupt current outputs or triggers new model calls unexpectedly.

Record audit run/Artifact/QE IDs, hashes, counts, warnings and provider/model provenance.

## STEP 9 — SOURCE-COPY VI + EN

Run current Source-copy v2 against the final visible VI and EN drafts and their current valid Assertion Audit outputs.

Hard requirement for each locale:

```text
fail_count = 0
```

`warn_count > 0` is allowed for this first operational package but must be surfaced verbatim to Founder.

Run one exact rerun per locale only for normal idempotency evidence. Do not stop on a benign reuse diagnostic if the canonical output is unambiguous and no unintended side effect/model call occurs; report it for post-operation hardening.

Record Source-copy eval/Artifact/QE IDs, result, warn/fail counts, max overlap and every warning finding.

## STEP 10 — OPERATIONAL PACKAGE V0

If all hard gates are clean, create two local deterministic files under:

```text
artifacts/operational/
```

Suggested names:

```text
ce05-first-operational-journal-<UTCSTAMP>.json
ce05-first-operational-journal-<UTCSTAMP>.md
```

Do NOT commit these generated production files to Git.

Package JSON must be canonical/sortable and include at minimum:

- `schema_version: 0`;
- package purpose/status = `READY_FOR_FOUNDER_OPERATIONAL_APPROVAL`;
- exact Founder question and selected angle title;
- ContentCase ID;
- source Journal ContentRun ID;
- SettingsSnapshot ID and resolved provider/model route;
- EvidenceSet ID/version/hash/status/approval ID/approver;
- selected Evidence IDs, source domains and short exact excerpts;
- OriginalityPack ID/snapshot hash/status/approved_by;
- VI final draft ID/version/hash + complete visible VI content;
- EN final draft ID/version/hash + complete visible EN content;
- VI Assertion Audit Artifact/QE/result/counts;
- EN Assertion Audit Artifact/QE/result/counts;
- VI Source-copy Artifact/QE/result/warn/fail/max overlap;
- EN Source-copy Artifact/QE/result/warn/fail/max overlap;
- combined `warnings` array containing every surviving non-critical warning verbatim with locale/location/source refs;
- hard-gate summary showing every hard blocker check as clean;
- `manual_publish_checklist`:
  - Founder reads VI + EN;
  - Founder accepts/rejects listed warnings;
  - Founder confirms title/formatting;
  - manual placement/publish only after explicit approval;
  - record final URL/location after placement;
  - record corrections made outside ContentEngine, if any;
- no secrets.

Markdown package is the human review view of the same data, with full VI/EN copy first and provenance/quality appendix after it.

Compute SHA-256 for both files and verify a second deterministic serialization from the same runtime state produces byte-identical package content (timestamp/name metadata must be excluded from the canonical payload hash or held constant for this check).

## T05.15 / T05.16 / T05.17 INTERPRETATION FOR THIS TASK

If the package is produced with all hard gates clean:

- Fresh acceptance supersedes the vanished historical UUID-bound T05.15 runtime requirement.
- T05.15 quality intent is **SATISFIED FOR THE FRESH OPERATIONAL CANDIDATE**.
- T05.16 Minimal Operational Package is **SUBSTANTIVELY COMPLETE** as Operational Package V0.
- T05.17 is **READY FOR FOUNDER OPERATIONAL APPROVAL / MANUAL CONTROLLED PLACEMENT**.

Do not publish automatically.

## FORBIDDEN

- no auto-publish;
- no WordPress adapter work;
- no new provider/model/agent role;
- no generic workflow/orchestration framework;
- no DB copy/restore merely to recreate historical UUIDs;
- no deleting historical records from any discovered DB;
- no fake Evidence, audit, QE, approval or pass result;
- no changing Assertion Audit/Source-copy thresholds;
- no secret output;
- no broad refactor;
- no T05.18–T05.22 implementation in this task.

## REQUIRED REPORT

Return one report containing:

```text
TASK ID: CE05-FAST-OPERATIONAL-RESET-LOCAL
START STATE
DATABASE RESOLUTION
PLANNING SPINE
EVIDENCE / EVIDENCESET
ORIGINALITY PACK
JOURNAL RUN / BUNDLE / ROUTE
ANGLE + PRE-AUTHORIZED SELECTION
OUTLINE / WRITERS / REVIEW-REVISE
VI ASSERTION AUDIT
EN ASSERTION AUDIT
VI SOURCE-COPY
EN SOURCE-COPY
SURVIVING WARNINGS
OPERATIONAL PACKAGE V0
  JSON path / SHA-256 / bytes
  Markdown path / SHA-256 / bytes
  deterministic reserialization check
HARD-GATE SUMMARY
SIDE EFFECT / IMMUTABILITY CHECK
OPERATOR NOTES
RISKS / BLOCKERS
STATUS: READY FOR FOUNDER OPERATIONAL APPROVAL | BLOCKED
```

Also paste the complete final VI and EN visible content in the report so MG/Founder can review without opening the DB.

## STOP CONDITIONS

Do **not** stop after a successful substep.

Stop only when:

- a hard blocker defined above occurs, in which case return `BLOCKED` with the exact first blocking condition and preserve all evidence; OR
- Operational Package V0 is complete, in which case return `READY FOR FOUNDER OPERATIONAL APPROVAL`.

After either condition, STOP.

NO SELF-DIRECTED NEXT TASK.