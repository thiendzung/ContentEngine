# CE04 PR-E — Architecture Decision

Date: 2026-09-07
Branch: `ce04-evidence-research-evidence-set`
Scope: T04.18–T04.23

## Decision 1 — Discovery and Evidence stay separate

Discovery answers:

`What looks worth investigating?`

Evidence Research answers:

`What can MOTGU actually support with traceable source content?`

Therefore:

- PR-D SEARCH signals remain planning signals;
- raw SERP/autocomplete/PAA/provider snippets are never directly promoted to factual Evidence;
- an external factual Evidence row requires successfully read content with an exact locator and excerpt;
- `evidence_eligible=false` Discovery artifacts remain non-evidence inputs.

## Decision 2 — ContentCase starts only after human selection

The selected O4 ContentOpportunity is now a legitimate content direction.

PR-E may create/reuse one ContentCase tied to:

- project `motgu`;
- persisted ContentOpportunity `068991ab-de34-4787-9c38-8935c3f0e2da`;
- NeedHypothesis `530bdd27-f008-4910-9b3b-df83e007cfa2`;
- content type `journal`.

The persistence service must be idempotent for this handoff. A rerun may not create a second ContentCase for the same selected opportunity.

NeedHypothesis remains `PROPOSED`; ContentExperiment remains `PLANNED`.

## Decision 3 — Reuse CE02 Claim/Evidence schema

Do not add parallel claim/evidence tables.

Use existing models:

- `Claim`;
- `Evidence`;
- `EvidenceSet`;
- `OriginalityPack`.

Existing Evidence relations are authoritative for PR-E:

- supports;
- contradicts;
- qualifies;
- context_only.

If docs still omit `qualifies`, synchronize docs to the implemented schema rather than deleting the existing relation.

## Decision 4 — Claims must be atomic and bounded

A claim candidate should express one checkable proposition wherever practical.

Examples of acceptable shape:

- one pricing factor can affect the asking price of an original artwork;
- gallery commission can be one component considered in pricing;
- materials, size, artist context or market context may be relevant depending on source support.

Do not create broad universal claims such as:

- one formula proves a fair art price;
- a price guarantees future appreciation;
- a specific percentage rule is universally correct.

Claim status starts unverified until linked evidence justifies a later status decision.

## Decision 5 — Evidence requires exact readable provenance

For external web evidence:

```text
Source
→ SourceDocument
→ optional KnowledgeChunk
→ Claim
→ Evidence(locator + excerpt + relation + provenance)
```

Validation must reject an excerpt that is not found in the referenced SourceDocument/KnowledgeChunk after canonical normalization.

Search/provider rank is not authority.

## Decision 6 — Contradictions are first-class

Research should not only collect support.

The workflow must be able to preserve:

- supports;
- contradicts;
- qualifies;
- context_only.

A research run with no contradiction may still complete, but it must record that contradiction coverage is missing rather than interpreting absence as agreement.

## Decision 7 — EvidenceSet is a versioned snapshot

EvidenceSet service contract:

```text
draft v1
→ validate evidence refs
→ deterministic content hash
→ explicit lock
→ immutable v1
```

If research changes after lock:

```text
locked v1
→ new draft v2
→ changed evidence refs
→ new content hash
→ explicit lock v2
```

Never mutate `evidence_ids_json`, content hash or lock identity of an already locked EvidenceSet through the PR-E service.

## Decision 8 — Originality is separate from external evidence

OriginalityPack answers:

`What does MOTGU itself have to add?`

It must not be populated by copying web research into MOTGU-owned material.

The builder may use approved/retrieved first-party MOTGU material. If none is available, produce a draft pack that clearly records an originality gap instead of inventing material.

## Decision 9 — Provider policy remains bounded

Reuse ProductionResearchRouter.

No default all-provider fanout.

Internal knowledge first, then bounded external route under existing PR-C policy. Jina or another existing reader must successfully read selected pages before external text is evidence-eligible.

No new provider in PR-E unless a real gate proves a concrete gap and MG CONTENT ENGINE explicitly approves it.

## Decision 10 — Harness integration stays optional and honest

PR-E workflow may run standalone for CE04 validation.

If a legitimate ContentRun/StepRun context is supplied, reuse CE03 budget/ToolCall telemetry and artifact persistence.

Do not create a fake ContentRun only to obtain telemetry.

## Final boundary

PR-E ends at EvidenceSet + OriginalityPack readiness.

Knowledge admission, Obsidian mirror and memory-gap admission belong to PR-F / T04.24–T04.31.

Journal angle/outline/draft belongs to CE05.