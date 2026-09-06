# TEAM LOG — CE02 CORE CONTENT DATA START

Date: 2026-09-06
Project: ContentEngine
Phase: CE02 — Core Data + Settings
PR: CE02 PR-A — Core Content Data
Branch: `ce02-core-content-data`
Base main: `e090d1a9c024fe3b5fb576dec2ccf3b9d4e3c3f4`

## GOAL

Persist the CE01 content-planning spine as real, versioned PostgreSQL data without changing the proven CE01 behavior.

```text
Project
→ Signal
→ NeedHypothesis
→ ContentOpportunity
→ HumanSelection
→ ContentExperiment
→ ContentCase
→ LocaleVariant
→ ContentItem
→ ContentVersion
```

## SCOPE

- SQLAlchemy declarative base and core content persistence models;
- explicit Alembic migration;
- foreign keys, unique constraints, checks and indexes needed by PR-A;
- review/selection history records;
- minimal persistence helpers for selection and content version creation;
- contract tests against PostgreSQL;
- CE01 regression must remain green.

## NON-GOALS

Do not add in PR-A:

- SettingsVersion / SettingsSnapshot;
- Prompt/Recipe registries;
- Brand/Language DNA storage;
- Source/SourceDocument/KnowledgeChunk;
- Claim/Evidence/EvidenceSet;
- OriginalityPack/Media persistence;
- ContentRun/StepRun/Artifact/ContextManifest;
- WordPress publishing;
- large UI or workflow automation.

## CONTRACT DECISIONS

1. IDs are generated once as UUIDs and are not recomputed from mutable text.
2. `ProblemDesire` and `AudienceSignal` are not created; canonical replacements are `NeedHypothesis` and `Signal`.
3. Search/market signals remain observations; human selection must not promote a NeedHypothesis.
4. NeedHypothesis support/contradiction links use a real relation table.
5. ContentOpportunity signal links use a real relation table.
6. NeedHypothesis reviews and HumanSelection are append-only history records, not overwrite-only fields.
7. Content identity is `ContentCase → LocaleVariant → ContentItem → ContentVersion`.
8. ContentItem keeps stable identity across edit/refresh; each material content change creates a new ContentVersion.
9. PR-A does not create placeholder foreign keys for future Run/Artifact records. Those links will be added by later migrations when those tables exist.
10. Migrations are explicit; do not use runtime `metadata.create_all()` as migration history.

## MIGRATION DECISIONS

- CE01 baseline migration stays unchanged.
- CE02 PR-A adds a new revision after `20260902_0001`.
- Upgrade creates only PR-A tables.
- Downgrade drops them in reverse dependency order.
- Alembic metadata is wired to the application declarative base for drift detection/autogenerate support later.

## ACCEPTANCE TESTS

- duplicate Project slug rejected;
- Signal locator/provenance validation works;
- founder-proposed NeedHypothesis may remain `PROPOSED`;
- UPDATE/REFRESH/MERGE/LINK_ONLY require an existing target;
- HumanSelection does not change NeedHypothesis status;
- ContentCase references the selected hypothesis/opportunity;
- duplicate LocaleVariant for the same case/locale rejected;
- ContentItem identity stays stable through refresh;
- duplicate ContentVersion number rejected;
- earlier ContentVersion rows remain unchanged;
- migration upgrade/downgrade/re-upgrade passes;
- CE01 Research/Opportunity tests remain green;
- full CI passes.

## CURRENT STATUS

Implementation started. No blocker identified at start.

## LESSONS / LOOP

- Keep database constraints for rules the database can prove; keep semantic validation in a small service where a portable SQL constraint would be brittle.
- Do not let persistence introduce a second business contract beside the already-tested CE01 in-memory contract.
