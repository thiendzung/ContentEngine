# CE05 PR-A architecture decision

Date: 2026-09-09
Branch: `ce05-journal-context-memory`

## Decisions

1. Reuse the existing immutable `Artifact` model for `memory_overlap` and
   `journal_context`; do not add parallel Journal artifact tables.
2. Extend the existing CE03 `ContextManifest` with the exact Journal context artifact
   and approved knowledge references so model-facing inputs remain reproducible.
3. Recall only `KnowledgeCandidate(status=APPROVED)` rows from the same project and
   compatible locale. Candidates without source refs or structured provenance are not
   eligible.
4. Use bounded deterministic token-overlap ranking for this PR-A. Provider calls,
   embeddings, and broad retrieval are deferred to the research handoff scope.
5. Treat Opportunity Map `MERGE`, `LINK_ONLY`, and `DO_NOT_WRITE` as authoritative in
   the effective memory decision; the Journal surface cannot silently convert them to
   `CREATE`.
6. Keep the initial Journal UI read-only and small: it selects existing cases and
   displays the assembled context without creating production content or side effects.
