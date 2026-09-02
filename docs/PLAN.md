# PLAN — CONTENTENGINE V1

## Phase CE00 — Foundation Contracts

Mục tiêu: khóa sản phẩm và kiến trúc trước code.

Deliverables:

- North Star;
- non-negotiables;
- architecture;
- data contract;
- settings contract;
- harness spec;
- memory/learning spec;
- quality spec;
- Journal spec;
- Artwork spec;
- publish/measure spec;
- AGENTS.md;
- implementation task map.

Exit gate:

- không còn ambiguity lớn về ownership, state, source of truth, approval, versioning, retry, idempotency.

## Phase CE01 — Repository Skeleton

Mục tiêu: tạo nền chạy được, chưa có AI workflow đầy đủ.

Deliverables:

- backend FastAPI skeleton;
- frontend Next.js skeleton;
- database connection + migrations;
- module boundaries;
- config/settings loader;
- health endpoints;
- test/lint/build pipeline;
- CI.

Exit gate:

- backend/frontend build;
- database migrate clean;
- tests pass;
- OpenAPI generation stable.

## Phase CE02 — Core Data + Settings

Deliverables:

- Project;
- versioned Settings + snapshot;
- Source/SourceDocument;
- Entity/Claim/Evidence;
- ContentBrief;
- ContentRun/StepRun/Artifact/Approval;
- ModelCall/QualityEvaluation;
- Settings UI tối thiểu.

Exit gate:

- create/read/version core data;
- run giữ settings snapshot bất biến.

## Phase CE03 — Durable Harness

Deliverables:

- run state machine;
- step runner;
- checkpoints;
- retry/error classes;
- approval pause/resume;
- budgets;
- model router interface;
- tool adapter interface;
- telemetry;
- restart/resume tests.

Exit gate:

- synthetic workflow survive restart;
- bounded retry;
- no duplicate side effects.

## Phase CE04 — Knowledge + Evidence

Deliverables:

- ingest pipeline;
- fingerprint/dedupe;
- canonical Markdown/text;
- chunking;
- entity refs;
- retrieval;
- Claim/Evidence ledger;
- authority rules;
- memory gap report.

Exit gate:

- same source ingest twice no duplicate;
- every retrieved item has provenance;
- unsupported claim detectable.

## Phase CE05 — Journal Engine V1

Deliverables:

- Brief UI;
- research workflow;
- angle generation/approval;
- outline;
- draft;
- review/revise;
- bilingual independent writers;
- final package.

Exit gate:

- one real MOTGU Journal runs end-to-end to final approval without publish.

## Phase CE06 — Quality + Golden Set

Deliverables:

- core evaluators;
- human evaluation UI;
- Golden/Weak fixtures;
- regression runner;
- candidate vs baseline report.

Exit gate:

- model/prompt/settings candidate cannot promote without regression report.

## Phase CE07 — Artwork Engine V1

Deliverables:

- canonical Artwork ingest/adapter;
- artwork brief/workflow;
- fact lock;
- artist intent distinction;
- bilingual output;
- related content/link package.

Exit gate:

- one real MOTGU Artwork content runs end-to-end with zero canonical fact drift.

## Phase CE08 — WordPress Publish + Measurement

Deliverables:

- WordPress draft adapter;
- idempotent mapping;
- Search Console import;
- Analytics import;
- Rank Math technical signal adapter if stable access exists;
- audience/content hypothesis mapping.

Exit gate:

- Journal + Artwork publish as drafts safely;
- metrics trace back to content hypothesis.

## Phase CE09 — Content Memory + Learning Loop

Deliverables:

- published content memory;
- duplicate/intent overlap check;
- human edit delta;
- learning candidates;
- audience signals;
- 1/3/6-month review reports.

Exit gate:

- system can explain what it learned and evidence behind each candidate without auto-changing production rules.

## Phase CE10 — Pilot

Run 10–20 hypothesis-driven contents.

Mục tiêu:

- kiểm chứng quality process;
- tìm failure modes;
- tune costs;
- tune approval load;
- establish first Golden Set;
- collect first real audience signals.

Không mở CRM/Sales Agent trước CE10 review.
