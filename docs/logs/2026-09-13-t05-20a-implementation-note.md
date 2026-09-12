# T05.20A implementation note

Implementation candidate lives on this branch and is intentionally read-only.

- Adds deterministic Journal review list/detail read model.
- Resolves approved content through ContentVersion.final_artifact_id.
- Resolves Assertion Audit and Source-copy only when bound to the exact approved bytes.
- Surfaces surviving warnings verbatim.
- Replaces the old context-only frontend workspace with a compact bilingual Review Console.
- Adds client-side Copy content only.
- Adds focused regressions for current-vs-historical audit selection, pending state, conflict fail-closed behavior, warnings, and read-only row counts.

No migration, approval mutation, ContentVersion mutation, model/provider/tool call, publishing action, WordPress action, or external side effect is introduced.
