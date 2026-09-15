# K6 — Journal KnowledgeBrief Binding

Date: 2026-09-15
Status: IMPLEMENTED / STACKED DRAFT
Base: K5 exact head `fb08ac2cc58c276b695f2dcd8234a423fd2c18d7`

## Goal

Make the deterministic K1–K5 knowledge subsystem usable by the real Journal model boundary without weakening CE05 evidence/originality authority or historical replay.

K6 binds one exact verified K5 `KnowledgeBrief` to one exact Journal `ContentRun`, freezes it into Journal context, and then materializes it into the actual Angle model input. A K5-bound Journal path must not perform legacy live `KnowledgeCandidate` keyword recall.

## Locked semantics

1. Existing historical Journal v1 context and legacy Start requests remain replayable.
2. K6 never guesses the current/latest brief. The operator Start request may explicitly supply one `knowledge_brief_id`.
3. A supplied brief is allowed only for `start`; retry/continue/resume/cancel cannot switch the run's brief.
4. Start binds the exact verified brief/hash to the exact ContentRun before Job enqueue.
5. The binding must match project, ContentCase and source locale; the database independently enforces the same scope and immutability.
6. Start idempotency includes `knowledge_brief_id` only when one is supplied. Legacy Start hashes therefore remain unchanged; same key + different brief fails closed.
7. Worker execution loads and revalidates the durable run binding. There is no `latest brief` lookup.
8. K5-bound context assembly performs **no live KnowledgeCandidate recall**.
9. The Journal context artifact freezes exact K5 ID, method, snapshot hash and canonical payload.
10. `ContextManifest` binds canonical `knowledge_brief:<uuid>:<sha256>`.
11. Runtime and Angle loading re-resolve the typed ref and immutable K5 lineage fail-closed.
12. The actual Angle model input receives the exact verified K5 payload, not telemetry-only metadata.
13. K5 reusable knowledge is context; it does **not** replace current EvidenceSet factual authority or OriginalityPack requirements.
14. No automatic research/refresh/policy action and no new human gate are introduced.

## Durable binding

Migration `20260915_0033` adds `journal_knowledge_brief_bindings` with exactly one binding per ContentRun.

The binding stores:

- ContentRun ID;
- ContentCase ID;
- LocaleVariant ID;
- KnowledgeBrief ID;
- exact KnowledgeBrief snapshot hash;
- binding actor.

A database trigger rejects update/delete and rejects any run/case/variant/project/locale/hash mismatch. The service layer revalidates the K5 lineage before creating or consuming the binding.

## Operator Start contract

`POST /journal/operator/cases/{content_case_id}/commands` accepts optional `knowledge_brief_id`.

When supplied:

- intent must be `start`;
- the exact brief becomes part of the command request hash;
- state/preflight checks still run before binding;
- binding is persisted before the Job is enqueued;
- exact command replay remains idempotent;
- same idempotency key with another brief is a conflict;
- later retry/continue cannot replace the immutable binding.

When omitted, historical Start behavior and request hashing remain unchanged.

The frontend is not allowed to choose stage/provider/model. K6 adds only an explicit knowledge-context binding input; it does not make model/runtime selection a browser concern.

## Versioning / compatibility

Legacy Journal context remains schema version 1.

A KnowledgeBrief-bound Journal context is schema version 2 and contains an additional `knowledge_brief` field. Existing v1 payload hashes do not change.

The existing `journal_input_bundle` schema remains unchanged. The exact K5 binding travels through the immutable Journal context + ContextManifest and is materialized into Angle model input from the verified manifest ref.

## Typed reference contract

Canonical typed ref:

`knowledge_brief:<brief_uuid>:<brief_snapshot_hash>`

- UUID must be canonical lowercase text;
- hash must be lowercase 64-character SHA-256;
- exactly zero or one KnowledgeBrief ref may exist in a ContextManifest;
- other existing `knowledge_chunk_refs` remain backward-compatible.

## Model-input budget

K5 storage itself may contain a larger immutable brief snapshot, but K6 refuses to place an unbounded payload into Journal model context.

The exact canonical `brief_json` allowed across the model boundary is capped at **32 KiB UTF-8 JSON**. Oversized payloads fail closed before downstream model execution with `knowledge_brief_ref_payload_too_large`.

This is a provider-neutral context-size guard; it is not a model token-limit claim.

## JournalContext contract

For K5-bound assembly:

- `schema_version = 2`;
- legacy `approved_knowledge` is empty;
- legacy `approved_knowledge_refs` is empty;
- no KnowledgeCandidate query is executed by the K5 branch;
- `knowledge_brief` contains exact K5 ID, method, snapshot hash and canonical verified payload;
- memory-overlap behavior and upstream CREATE/MERGE/LINK_ONLY/DO_NOT_WRITE authority remain unchanged.

## Angle model boundary

When ContextManifest contains the typed KnowledgeBrief ref, actual Angle input contains:

```text
knowledge_brief:
  id
  method
  snapshot_hash
  payload
```

The worker path is proven end-to-end in tests:

`operator Start -> durable run binding -> worker load/revalidation -> Journal context v2 -> ContextManifest typed ref -> Angle model input`.

## Non-goals

- no automatic KnowledgeBrief selection or “latest brief” policy;
- no provider/model selection in frontend;
- no automatic external research or source refresh;
- no EvidenceSet or OriginalityPack weakening;
- no vector DB / embeddings;
- no generated free-form knowledge summary;
- no new human gate;
- no operational migration/data mutation as part of CI proof.

## Acceptance

Automated proof covers:

1. legacy Journal context remains schema v1;
2. K5-bound context is schema v2 and skips legacy live candidate recall;
3. exact K5 ID/method/hash/payload are frozen;
4. ContextManifest carries canonical typed ref;
5. malformed/forged/multiple refs fail closed;
6. wrong project/case/locale fails closed;
7. corrupted K5/K4/K3 lineage fails closed;
8. 32 KiB model-bound payload budget fails closed;
9. operator Start creates the exact immutable run binding before Job enqueue;
10. idempotent replay requires the same brief and same command payload;
11. retry/continue cannot switch brief;
12. worker consumes the Start-created binding and the exact verified brief reaches `angle_model_input`;
13. EvidenceSet and OriginalityPack checks remain mandatory;
14. migration `0032 -> 0033` round-trip passes;
15. full repository CI passes on the exact final head.

## Safety

No operational migration or operational data mutation is authorized by this PR. All schema/data proof runs only against disposable CI/test databases. Do not merge or apply operationally without Founder authorization.
