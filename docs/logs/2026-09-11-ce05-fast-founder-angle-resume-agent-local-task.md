# CE05 — Founder-Locked Angle Fast Resume — Agent Local Task

Date: 2026-09-11

## TASK ID

`CE05-FAST-FOUNDER-ANGLE-RESUME-LOCAL`

## OWNER

Agent Local executes. MG reviews only the final Operational Package V0 or a hard blocker. Founder owns final operational content approval.

## OBJECTIVE

Resume the already-valid fresh CE05 candidate after the observed Angle model provenance failure without changing the prompt, adding a migration, weakening validation, or calling the Angle model again.

The Founder already locked the exact product direction. Materialize that human decision deterministically on a fresh replacement Journal run, then continue without intermediate stops through Operational Package V0.

## BASE / PRECONDITIONS

Execute only after the PR containing this task is merged.

Start from clean synchronized `main` using the standard repository sync contract. Unexpected local changes => `BLOCKED`; never auto reset/stash/delete/overwrite.

Required runtime snapshots must still validate exactly:

- DB: configured `contentengine`;
- migration: `20260910_0022 (head)`;
- ContentCase: `d29fe3a3-1482-4364-92b1-19cd5be595a3`;
- NeedHypothesis: `80afc3bb-d768-4cd6-80d5-04f1ef022bc2` / `PROPOSED`;
- ContentOpportunity: `b012e8b6-95b1-4a15-bcd4-1a6abf1dcfd2`;
- SettingsSnapshot: `989debbf-5970-44d2-baeb-a605c75e99d6`;
- locked EvidenceSet: `48791ec3-bfc0-46fb-9294-eaf46754f8de` / v3 / hash `952dce90b82f6aeff17bbbaf26a0d16fdcacffe2243a1dc018f2f8c58dfc8eff`;
- EvidenceSet approval: `c0056bb2-390b-441f-8786-29fd748ab353`;
- approved OriginalityPack: `4ec19fe4-ebbf-4159-bef3-791bff71eb0a` / hash `618039f1fe24d31a239222b56451939c250492a36ec85253475d618517b74507` / 4 usable items;
- VI LocaleVariant: `a09487eb-ade6-4a0b-ac29-b4c42e33f53a`;
- EN LocaleVariant: `d75072ec-8392-4628-a843-8e4075b7ab99`.

Historical failed diagnostic run must remain immutable:

- ContentRun `36581e66-e537-4033-b717-52b7ce17043c` = `failed`;
- failure `angle_generation_failed`;
- bundle `4515b4d5-d785-4552-9473-38b5d2d19c00` / v1 / hash `538347ef77ac552d349c7ebe952a6e45ee2f05db4dce396df74792173294b209`;
- two failed-validation Angle ModelCalls remain historical diagnostics.

Do not resurrect, mutate, delete, repair, or attach new downstream outputs to that failed run.

## ROOT CAUSE / OPERATING DECISION

The Angle prompt supplies each OriginalityPack item with both `source_ref` and `approval_ref`, while the Angle validator accepts only exact `source_ref` values in `originality_refs`. Two bounded model attempts returned refs outside the allowed source-ref set and correctly failed closed.

For the first operational Journal, do NOT change prompt/registry/migration and do NOT call the Angle model again.

The Founder decision is already explicit and locked:

`A First-Time Buyer’s Checklist for Understanding an Artwork’s Price`

Use the existing `AngleCandidate`, `load_journal_input_bundle()`, `persist_angle_candidates()`, `angle_candidate_hash()`, `approve_angle_candidate()` and `handoff_approved_angle()` contracts. `persist_angle_candidates()` explicitly supports `model_calls=0`; all Evidence/Originality refs still pass the current exact validator.

## STEP 1 — CREATE/REUSE ONE REPLACEMENT JOURNAL RUN

Create or reuse exactly one non-failed replacement Journal ContentRun for the same ContentCase and exact SettingsSnapshot using the existing harness lifecycle. Do not create a second replacement if an exact compatible one already exists from an interrupted retry.

Build a fresh immutable `journal_input_bundle` for that replacement run from the same exact selected ContentOpportunity, locked EvidenceSet v3, approved OriginalityPack and SettingsSnapshot. Research decision remains `REUSE_EXISTING`; this replacement step performs zero provider/model/tool calls.

Require the replacement run/bundle to revalidate all upstream hashes and lineage. Before Angle materialization, place the replacement run in the normal state accepted by the downstream Outline path (`waiting_approval` under the current merged lifecycle).

If no standalone CLI fits fresh IDs, use one temporary local Python invocation from `backend/` that calls existing merged public services/models only. Do not create repository orchestration code.

## STEP 2 — DETERMINISTIC FOUNDER-LOCKED ANGLE MATERIALIZATION

Load the fresh replacement bundle and derive, from the validated bundle itself:

- `evidence_refs = tuple(str(id) for id in bundle.evidence_ids)`;
- `originality_refs = bundle.originality_refs`.

Do not type or reconstruct refs manually. Require exactly the 9 locked Evidence refs and the 4 exact OriginalityPack `source_ref` values.

Materialize exactly these three schema-valid candidates. For every candidate, use the complete exact `evidence_refs` and `originality_refs` derived above.

### Candidate 1 — SELECT THIS

```text
angle_id: founder-angle-01
working_title: A First-Time Buyer’s Checklist for Understanding an Artwork’s Price
reader_problem: A first-time buyer can see an asking price but may not know which facts and context matter before deciding whether that price makes sense for the specific purchase.
central_question: How do I know if an original artwork is fairly priced?
core_promise: Give the reader a practical checklist for separating work-specific facts, practical transaction costs, availability, market context, and the buyer’s own decision without pretending there is a universal pricing formula.
point_of_view: Start with verifiable facts about the work, then understand practical and market context, then make a calm personal decision.
why_now: The checklist is useful before a first purchase because price alone does not explain the work, transaction context, or whether the decision is right for the buyer.
confidence: 1.0
locale: bundle.locale
```

### Candidate 2 — NON-SELECTED CONTRACT ALTERNATIVE

```text
angle_id: founder-angle-02
working_title: Questions to Ask Before an Artwork’s Price Makes Sense to You
reader_problem: A first-time buyer may not know what to ask before accepting an artwork price at face value.
central_question: What should I ask before deciding whether an artwork’s price makes sense?
core_promise: Turn the available evidence and MOTGU guardrails into a short sequence of factual and practical questions for a first-time buyer.
point_of_view: Ask for context first; do not convert appraisal context into a universal consumer valuation rule.
why_now: A question-led approach helps a buyer identify missing information before making a purchase decision.
confidence: 0.8
locale: bundle.locale
```

### Candidate 3 — NON-SELECTED CONTRACT ALTERNATIVE

```text
angle_id: founder-angle-03
working_title: What an Artwork’s Price Can — and Cannot — Tell a First-Time Buyer
reader_problem: A first-time buyer may overread the asking price as if it were a complete statement of value or quality.
central_question: What can an artwork’s asking price tell me, and what still needs context?
core_promise: Separate what the asking price shows from work facts, transaction costs, market context, and personal preference.
point_of_view: Treat price as one piece of context, not as a universal verdict about the artwork.
why_now: This framing helps prevent false certainty while keeping the buying decision practical and low pressure.
confidence: 0.8
locale: bundle.locale
```

For all three candidates use exactly:

```text
excluded_claims:
- universal pricing formula
- investment or appreciation promise
- luxury or status framing
- fake scarcity or urgency
- unverified live artwork, artist, price, availability or location facts

risks:
- appraisal context could be mistaken for a consumer valuation rule
- live artwork-specific data may be absent and must not be invented
```

Persist through the existing `persist_angle_candidates()` function with truthful deterministic provenance:

```text
provider = founder_decision
model = deterministic_materialization
model_calls = 0
provider_calls = 0
generator_version = ce05.founder_locked_angle.v1
schema_version = 1
```

This is NOT a model route and MUST NOT create a ModelCall or ToolCall.

Create a normal dedicated Angle StepRun on the replacement run so the deterministic Artifact has explicit step ownership and input/output refs. Use the existing harness lifecycle; do not attach it to the failed run.

Run the exact deterministic materialization a second time and require reuse of the same Angle Artifact with zero new Artifact/ModelCall/ToolCall side effects.

## STEP 3 — PERSIST THE EXISTING FOUNDER DECISION

Compute the exact candidate hash for `founder-angle-01` via `angle_candidate_hash()`.

Approve that exact candidate through `approve_angle_candidate()` using:

```text
approved_by = founder
approval_reason = Pre-authorized Founder checklist direction for CE05 first operational Journal; deterministically materialized after Angle model reference failure.
```

Immediately verify through `handoff_approved_angle()`.

Exact approval rerun must reuse the same approval or otherwise remain zero-side-effect/idempotent under the merged approval contract.

Do not select candidate 2 or 3.

## STEP 4 — CONTINUE DIRECTLY TO OPERATIONAL PACKAGE V0

After the deterministic Angle approval PASS, continue the same replacement run through the remaining merged CE05 path without stopping after successful intermediate gates:

```text
Outline
→ VI Writer
→ EN Writer
→ Review/Revise VI + EN
→ Assertion Audit VI + EN
→ Source-copy VI + EN
→ Operational Package V0
```

Use the existing approved `codex_cli / gpt-5.6-luna` no-tool route only for the downstream model-backed steps that already require it. Do not treat the deterministic Angle provenance labels as a model route.

Reuse the existing fresh LocaleVariants. Use current scripts when they accept fresh IDs/hashes; otherwise use temporary local Python calls into the same merged public services. Do not create repo code merely to orchestrate.

Normal bounded validation retries defined by existing contracts are allowed. Do not add speculative cleanup code.

## HARD GATES

Stop only if one of these occurs:

- upstream snapshot/provenance/hash mismatch;
- replacement run cannot be created/revalidated without destructive mutation;
- deterministic Angle cannot pass the CURRENT exact candidate validator using refs derived from the bundle itself;
- Angle approval/handoff fails exact snapshot validation;
- Assertion Audit result = `fail` or critical unsupported/contradicted count > 0;
- Source-copy `fail_count > 0`;
- final VI or EN visible content is missing;
- unapproved model/tool capability is required;
- secret exposure or destructive/unbounded mutation would be required.

Non-critical warnings continue and are preserved verbatim in Operational Package V0.

Benign idempotency diagnostics do not block the first operation if there is one unambiguous canonical output and zero unintended model/provider/tool side effects; record them for post-operation hardening.

## OPERATIONAL PACKAGE V0

Use the same package contract in `docs/logs/2026-09-11-ce05-fast-operational-reset-agent-local-task.md`.

Package must additionally record:

- failed historical Angle run ID/failure code as diagnostic history;
- replacement Journal run ID;
- deterministic Angle generator `ce05.founder_locked_angle.v1`;
- `provider=founder_decision`, `model=deterministic_materialization`, `model_calls=0` for Angle only;
- selected `founder-angle-01` candidate hash and AngleApproval ID;
- reason: Founder direction was already locked; model Angle output failed exact OriginalityPack ref validation twice; no third Angle model call was needed.

Generated package remains local under `artifacts/operational/`; do not commit it.

## FORBIDDEN

- no new research or URL reads;
- no EvidenceSet or OriginalityPack mutation;
- no prompt/recipe/settings migration;
- no Angle model call;
- no normalization of invalid historical model refs into valid refs;
- no resurrection/modification/deletion of failed run `36581e66-e537-4033-b717-52b7ce17043c`;
- no application-code change;
- no generic orchestration/workflow framework;
- no WordPress integration;
- no auto-publish;
- no T05.18–T05.22 work.

## REQUIRED REPORT

Return one report containing:

```text
TASK ID
START STATE
UPSTREAM SNAPSHOT PREFLIGHT
FAILED ANGLE RUN PRESERVATION
REPLACEMENT JOURNAL RUN / BUNDLE
DETERMINISTIC ANGLE ARTIFACT
ANGLE IDEMPOTENCY
FOUNDER ANGLE APPROVAL / HANDOFF
OUTLINE
VI FINAL DRAFT
EN FINAL DRAFT
VI ASSERTION AUDIT
EN ASSERTION AUDIT
VI SOURCE-COPY
EN SOURCE-COPY
SURVIVING WARNINGS
OPERATIONAL PACKAGE V0 JSON / MARKDOWN / SHA-256
SIDE EFFECTS / MODEL / TOOL COUNTS
OPERATOR NOTES
RISKS / BLOCKERS
STATUS
```

If all hard gates are clean and package exists:

`STATUS: READY FOR FOUNDER OPERATIONAL APPROVAL`

Otherwise stop only at the first true hard blocker and report exact evidence.

NO SELF-DIRECTED NEXT TASK after package/blocker. Do not publish.