# CE05 — Journal Engine V1

## North Star

CE05 proves one real, reviewable Journal path:

```text
selected opportunity
→ ContentCase + LocaleVariant
→ bounded JournalContext
→ approved angle
→ approved outline
→ draft
→ assertion/source checks
→ bounded revision
→ final human approval
→ ContentVersion
```

CE05 reuses CE02 data and CE03 durable harness. It does not create a second workflow
engine, and it does not let a writer search or research independently.

## JournalContext

The writer-facing context is a bounded artifact containing:

- selected `ContentOpportunity` and `NeedHypothesis`;
- `ContentCase` and one `LocaleVariant`;
- only `KnowledgeCandidate` rows with `status=APPROVED`, with source refs and provenance;
- the deterministic Content Memory overlap result;
- exact refs and the content hash of the assembled context.

Unapproved, rejected, missing-provenance, cross-project, cross-locale, or unselected inputs
block context assembly. Provider calls are not part of PR-A.

`MERGE`, `LINK_ONLY`, and `DO_NOT_WRITE` from the Opportunity Map remain authoritative;
the Journal surface cannot turn them into `CREATE`.

## Artifact and manifest contract

PR-A persists `memory_overlap` and `journal_context` through the existing immutable
`Artifact` model. A CE03 `ContextManifest` binds the exact context artifact and approved
knowledge refs. Repeating the same input reuses the same artifacts and produces an
equivalent manifest hash.

## Human gates

There are exactly three mandatory human gates:

1. approved angle;
2. approved outline;
3. final content approval before creating the final `ContentVersion`.

An artifact version change invalidates its previous approval.

## PR map

| PR | Scope |
|---|---|
| PR-A | Journal context, approved knowledge recall, memory overlap |
| PR-B | Research handoff, EvidenceSet, OriginalityPack, angle, outline |
| PR-C | Independent Vietnamese/English writers and bounded revision |
| PR-D | Assertion audit, source-copy check, final package |
| PR-E | One real Journal gate, review surface, metrics, closeout |

## PR-A acceptance

- ContentCase/LocaleVariant Journal surface is selectable in the small UI;
- internal recall is bounded and uses approved knowledge only;
- memory overlap is persisted as an artifact and does not mutate production content;
- context artifact and ContextManifest are reproducible;
- retrying the same input does not duplicate PR-A artifacts;
- tests use the dedicated test database and no research/provider call is made.

## Non-goals

No auto-publish, scheduler, vector database, multi-agent swarm, full SEO score, Artwork
writer, large dashboard, new research provider, or automatic learning/prompt changes.

## CQ-01 promise coverage extension

For new Founder-authored Journal intake, `promise` is not sufficient by itself. The
Founder/editorial brief also supplies 1..12 ordered `coverage_requirements` that state
which subject areas must not silently disappear while the model narrows the content.

Canonical flow:

```text
ContentOpportunity.coverage_requirements_json
→ exact journal opportunity snapshot (coverage-1..N)
→ Evidence Research extraction topics
→ Angle candidate: each ID = covered | reduced + rationale
→ Founder Angle decision
→ Outline: every covered ID maps to >=1 section
→ Founder Outline decision
```

Rules:
- a requirement may be intentionally reduced only at the visible Angle gate;
- missing, duplicated or unknown Angle requirement IDs fail closed;
- Outline may never map an ID the approved Angle marked `reduced`;
- all `covered` IDs must be mapped at least once before an Outline is persistable;
- exact IDs are bound dynamically into the Agent Bridge structured-output schemas;
- no second prompt/recipe registry generation is required for CQ-01;
- historical opportunities with no coverage contract remain readable and are not
  backfilled with invented Founder intent;
- CQ-01 does not yet define Pillar/Cluster editorial behavior, section-level evidence
  adequacy or Human Voice semantics; those belong to later Content Quality slices.

