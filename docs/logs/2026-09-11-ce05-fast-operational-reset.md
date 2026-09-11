# CE05 — Fast operational reset

Date: 2026-09-11
Owner: Founder + MG Content Engine
Status: ACTIVE DECISION

## Why this exists

After PR #53 merged, the configured runtime database `contentengine` was verified to contain zero `ContentCase`, `ContentRun`, `Artifact`, and `QualityEvaluation` rows. The historical CE05 O4 lineage therefore cannot be resumed in that configured database.

Continuing to repair code around historical UUIDs would optimize for a vanished environment rather than getting MOTGU into operation.

## Decision

Use **fresh operational acceptance**.

The historical O4 UUID-bound runtime is retained as development/history evidence, but it is no longer a prerequisite for the first operational Journal when those rows are absent from the active runtime database.

The quality guarantees remain; the old row identities do not.

```text
old rule
exact historical UUIDs -> finish T05.15 -> package -> operate

new fast rule
active runtime DB -> fresh candidate -> hard quality gates -> operational package -> Founder approval -> operate
```

Do not recreate historical rows merely to make old IDs exist. Do not copy fake audit/evaluation rows into the new database.

## One cheap recovery check

Before fresh bootstrap, Agent Local may perform one read-only scan of accessible local non-template PostgreSQL databases for the exact historical markers. If exactly one non-test database contains the complete locked lineage and is migration-compatible, it may be used for this operational task via an ephemeral environment override; do not edit `.env` or copy data.

If no complete candidate exists, immediately continue on the configured `contentengine` database. Do not stop merely because historical IDs are absent.

## Founder-locked product direction

The first operational Journal keeps the already-decided direction:

- framing: `How do I know if an original artwork is fairly priced?`
- audience: first-time art buyer;
- angle direction: `A First-Time Buyer’s Checklist for Understanding an Artwork’s Price`;
- no universal pricing formula;
- separate market facts from personal purchase decisions;
- no investment, appreciation, luxury, scarcity, or pressure framing.

These decisions may be reused for the fresh candidate without another intermediate Founder selection round. When a generated opportunity/angle requires a machine-selectable choice, the exact deterministic selection rule in the Agent Local task is pre-authorized by Founder/MG and is not an Agent Local product decision.

## Operational quality rule — finish first, perfect later

For the first controlled operational Journal, only **hard** quality failures block packaging.

Hard blockers:

- structural/provenance/hash/lineage validation failure;
- invalid or unlocked/unapproved EvidenceSet or OriginalityPack at Journal handoff;
- Assertion Audit has any critical unsupported or contradicted assertion, or deterministic result `fail`;
- Source-copy has any `fail` finding (12+ exact contiguous tokens under v2 rules);
- unapproved provider/tool/research capability;
- missing final visible locale content;
- data-integrity mutation outside the bounded run.

Non-critical `warn` findings do **not** automatically block the first operational package. They must be listed verbatim in the package and surfaced to Founder for final human acceptance/rejection.

Do not weaken the underlying Assertion Audit or Source-copy evaluators. This is an orchestration/operating decision only.

## Fast operational path

```text
resolve active DB
-> bootstrap fresh Founder-selected planning spine if needed
-> Evidence Research (bounded, strong-source query)
-> curate + approve + lock EvidenceSet
-> create + approve OriginalityPack from already-approved MOTGU guardrails
-> fresh Journal ContentRun + journal_input_bundle
-> Angle generation; deterministic pre-authorized selection toward locked checklist direction
-> Outline
-> VI + EN writers
-> Review/Revise
-> Assertion Audit VI + EN
-> Source-copy VI + EN
-> require NO HARD FAIL
-> export deterministic Operational Package V0 (JSON + Markdown + SHA-256)
-> STOP only for Founder final operational approval
-> manual controlled publish/place
-> observation log
-> then harden from real operation
```

## Operational Package V0

For the first operational smoke, a deterministic file package is sufficient to reach Founder review and manual controlled placement. Formal `ContentVersion` persistence/UI polish may be completed immediately after the first real operation unless existing code already supports it without adding a new implementation cycle.

Package must contain:

- exact VI and EN visible content;
- source draft IDs/versions/hashes;
- Assertion Audit Artifact/QE IDs and results;
- Source-copy Artifact/QE IDs and results;
- all warning findings;
- EvidenceSet and OriginalityPack IDs/versions/hashes/approval state;
- SettingsSnapshot and model route refs;
- ContentCase/ContentRun IDs;
- manual placement checklist;
- package SHA-256.

No automatic publishing is authorized.

## Stop policy

Do not stop after successful Discovery, Evidence, Angle, Outline, Writer, Review, Audit, or Source-copy substeps. Continue through the bounded path in the same task.

Stop only when:

1. a hard quality/data-integrity/security blocker occurs; or
2. the deterministic Operational Package V0 is ready for Founder final approval.

This decision supersedes the historical requirement that the first operational Journal must reuse the vanished O4 runtime UUIDs.