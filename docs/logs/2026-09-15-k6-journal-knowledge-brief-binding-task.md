# K6 — Journal KnowledgeBrief Binding

Date: 2026-09-15
Status: ACTIVE / STACKED DRAFT
Base: K5 exact head `fb08ac2cc58c276b695f2dcd8234a423fd2c18d7`

## Goal

Make the deterministic K1–K5 knowledge subsystem usable by the real Journal model boundary without weakening CE05 evidence/originality authority or historical replay.

K6 binds one exact verified K5 `KnowledgeBrief` into a Journal context and then into the actual Angle model input. A K5-bound Journal path must not perform the legacy live `KnowledgeCandidate` keyword recall.

## Why this slice exists

Before K6, K1–K5 can produce an immutable KnowledgeBrief, but CE05 `build_journal_context()` still performs live approved-candidate recall. `ContextManifest` records knowledge references, while the Angle model input receives only manifest metadata plus EvidenceSet/Originality content. Therefore K1–K5 would otherwise remain a parallel subsystem rather than a real model-facing input.

K6 closes that integration gap.

## Locked semantics

1. Existing historical Journal context/bundle behavior remains valid and replayable.
2. A K5-bound Journal context is explicit: the caller supplies one `knowledge_brief_id`; K6 does not guess which brief is current.
3. The K5 brief must verify successfully and match the Journal ContentCase project, exact ContentCase ID and exact locale.
4. K5-bound context assembly performs **no live KnowledgeCandidate recall**.
5. The Journal context artifact freezes the exact K5 brief ID, method, snapshot hash and canonical K5 payload.
6. `ContextManifest` binds a typed immutable ref `knowledge_brief:<uuid>:<sha256>`.
7. Runtime validation resolves and verifies typed KnowledgeBrief refs fail-closed before persisting a manifest.
8. Angle input loading resolves the exact bound KnowledgeBrief again and injects its canonical K5 payload into the actual model-facing `angle_model_input`.
9. A ref/hash mismatch, wrong project/case/locale, corrupted K5 parent or multiple KnowledgeBrief refs blocks the model boundary.
10. K5 reusable knowledge is context; it does **not** replace CE05 EvidenceSet factual authority. Angle candidates must still cite the exact current EvidenceSet according to existing validators.
11. K5 research/refresh/policy actions are informative deterministic context in this slice. K6 does not auto-run research, refresh sources or invent freshness policy.
12. No new human gate.

## Versioning / compatibility

The legacy Journal context remains schema version 1.

A KnowledgeBrief-bound Journal context is schema version 2 and contains an additional `knowledge_brief` field. Existing v1 payload hashes must not change.

The existing `journal_input_bundle` schema remains unchanged in K6. The exact K5 binding travels through the immutable Journal context + ContextManifest and is materialized into the Angle model input from the verified manifest ref. This avoids rewriting historical input-bundle semantics.

## Typed reference contract

Canonical typed ref:

`knowledge_brief:<brief_uuid>:<brief_snapshot_hash>`

- UUID must be canonical lowercase text.
- hash must be lowercase 64-character SHA-256.
- exactly zero or one KnowledgeBrief ref may exist in a ContextManifest.
- other existing `knowledge_chunk_refs` remain backward-compatible and are not reinterpreted by K6.

## JournalContext contract

For K5-bound assembly:

- `schema_version = 2`;
- legacy `approved_knowledge` is empty;
- legacy `approved_knowledge_refs` is empty;
- no KnowledgeCandidate query is executed by the K5 branch;
- `knowledge_brief` contains exact K5 ID, method, snapshot hash and canonical verified payload;
- memory-overlap behavior and upstream CREATE/MERGE/LINK_ONLY/DO_NOT_WRITE authority remain unchanged.

## Angle model boundary

When the bound ContextManifest contains the typed KnowledgeBrief ref, the actual Angle input contains:

```text
knowledge_brief:
  id
  method
  snapshot_hash
  payload   # exact verified K5 brief_json
```

The model input hash therefore changes when and only when the exact bound K5 semantic snapshot changes (along with existing model-input dependencies).

## Non-goals

- no automatic KnowledgeBrief selection policy;
- no operator/UI selector for internal stage/provider/model/brief identity;
- no external research execution;
- no source refresh execution;
- no model call in acceptance tests;
- no EvidenceSet or OriginalityPack weakening;
- no migration unless a durable schema change is proven necessary;
- no vector DB / embeddings;
- no generated knowledge summary;
- no new human gate.

## Acceptance

Automated proof must cover at minimum:

1. legacy Journal context remains schema v1 and existing tests stay green;
2. K5-bound Journal context is schema v2 and does not use legacy live approved-candidate recall;
3. exact K5 ID/method/hash/payload are frozen into context artifact;
4. ContextManifest carries the canonical typed KnowledgeBrief ref;
5. runtime rejects malformed/forged/multiple typed refs;
6. runtime rejects wrong-project/wrong-case/wrong-locale K5 binding;
7. corrupted K5/K4/K3 lineage fails closed;
8. Angle loader injects the exact verified K5 payload into actual `angle_model_input`;
9. model-input hash is bound to K5 snapshot hash;
10. stale/unknown/unclassified items do not appear in K5 `reusable_knowledge` model section (inherited K5 invariant, re-proven at integration boundary);
11. existing EvidenceSet and OriginalityPack checks remain mandatory;
12. exact replay of the same K5-bound context reuses equivalent immutable artifacts/manifests and does not duplicate semantic side effects;
13. no provider/model/external research call is required for K6 proof;
14. full repository CI remains green.

## Safety

No operational migration or operational data mutation is authorized. K6 is code/test integration only unless a later explicitly approved migration becomes necessary.