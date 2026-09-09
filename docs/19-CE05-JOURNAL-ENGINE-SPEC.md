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
