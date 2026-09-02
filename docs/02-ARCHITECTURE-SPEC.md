# 02 — ARCHITECTURE SPEC

## 1. Mục tiêu kiến trúc

Kiến trúc phải phục vụ một việc trước tiên: tạo Journal và Artwork content chất lượng cao cho MOTGU, có thể kiểm tra, đo, học và cải thiện theo thời gian.

Không tối ưu cho độ tổng quát tối đa ở V1.

## 2. Kiến trúc logic

```text
Configuration Layer
    ↓
Knowledge & Evidence Layer
    ↓
Retrieval / Context Builder
    ↓
Durable Run Harness
    ↓
Content Workflows
    ↓
Quality / Human Approval
    ↓
Publish Adapter
    ↓
Measurement
    ↓
Learning Loop
```

## 3. Các bounded modules

### 3.1 `system`

Sở hữu:

- project settings;
- model/provider configuration;
- secrets references;
- feature flags;
- versioned configuration.

Không sở hữu content workflow business logic.

### 3.2 `knowledge`

Sở hữu:

- source registry;
- source ingest;
- canonical document representation;
- fingerprints/dedupe;
- chunks;
- entities;
- claims/evidence;
- retrieval;
- content memory index.

### 3.3 `harness`

Sở hữu:

- Run;
- StepRun;
- state machine;
- checkpoints;
- resume/retry;
- budgets;
- model/tool call telemetry;
- approval pause/resume;
- cancellation.

Harness không sở hữu Journal-specific prompt hoặc Artwork-specific logic.

### 3.4 `content_engine`

Sở hữu workflow business logic:

- Brief;
- Research;
- Evidence selection;
- Angle;
- Outline;
- Draft;
- Review;
- Final package.

Bên trong chia `journal` và `artwork` theo vertical slice khi logic khác nhau.

### 3.5 `evals`

Sở hữu evaluator contract và kết quả:

- evidence/factual;
- brand voice;
- usefulness;
- originality;
- structure/readability;
- search/AI readability;
- internal linking;
- regression.

Evaluator không tự publish.

### 3.6 `learning`

Sở hữu:

- human edit deltas;
- content performance snapshots;
- audience signals;
- learning candidates;
- approved learnings;
- experiments;
- Golden Set metadata.

### 3.7 `publishing`

Sở hữu adapters:

- WordPress;
- future outputs.

V1 WordPress adapter phải idempotent và không làm thay đổi source-of-truth ngoài contract đã duyệt.

### 3.8 `measurement`

Sở hữu normalized metrics từ:

- Search Console;
- Analytics;
- Rank Math/WordPress technical checks khi có đường truy cập phù hợp;
- MOTGU-defined conversion events.

Measurement chỉ cung cấp signal, không tự thay đổi strategy.

## 4. Kiến trúc triển khai đề xuất

Giữ nền đã có từ prototype trước nếu tái sử dụng được:

- Backend: Python + FastAPI;
- Frontend: Next.js + React;
- relational database: PostgreSQL production, SQLite chỉ cho local/dev khi phù hợp;
- object/text artifact: Markdown/JSON files hoặc object storage tùy artifact;
- WordPress: external canonical publishing target.

Không đưa Rust/Tauri từ OpenHuman vào ContentEngine V1.

## 5. Repository target structure

```text
ContentEngine/
├── AGENTS.md
├── README.md
├── docs/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   └── modules/
│   │       ├── system/
│   │       ├── knowledge/
│   │       ├── harness/
│   │       ├── content_engine/
│   │       │   ├── journal/
│   │       │   └── artwork/
│   │       ├── evals/
│   │       ├── learning/
│   │       ├── publishing/
│   │       └── measurement/
│   ├── migrations/
│   ├── scripts/
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── features/
│       └── lib/
├── evals/
│   ├── golden/
│   ├── fixtures/
│   └── reports/
└── scripts/
```

## 6. Durable Run Graph

Không dùng một request HTTP kéo dài để chạy cả bài.

Mỗi content job được biểu diễn bằng graph/state machine:

```text
BRIEF
  ↓
KNOWLEDGE_RECALL
  ↓
RESEARCH
  ↓
EVIDENCE_LOCK
  ↓
ANGLE
  ↓
[HUMAN APPROVAL]
  ↓
OUTLINE
  ↓
[HUMAN APPROVAL optional/required by setting]
  ↓
DRAFT
  ↓
REVIEW
  ↓
REVISE (bounded loop)
  ↓
QUALITY_GATE
  ↓
[FINAL HUMAN APPROVAL]
  ↓
PACKAGE
  ↓
PUBLISH
  ↓
MEASURE
```

Mỗi node phải ghi output trước khi chuyển state.

## 7. State machine tối thiểu

`Run.status`:

- `pending`
- `running`
- `waiting_approval`
- `completed`
- `failed`
- `cancelled`

`StepRun.status`:

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`
- `waiting_approval`

Không biểu diễn retry bằng cách overwrite lịch sử lỗi; mỗi attempt phải có record hoặc attempt counter + error log đủ truy nguyên.

## 8. Idempotency

Các operation có side effect phải nhận `idempotency_key` hoặc suy ra stable key.

Ví dụ:

- source ingest: `(source_type, external_id, content_hash)`;
- publish: `(project_id, content_id, locale, target)`;
- metric import: `(provider, entity_id, metric_date, metric_name)`.

## 9. Context Builder

Context được build theo task, không theo kiểu dump tất cả.

Thứ tự ưu tiên:

1. system safety/operating rules;
2. approved project/brand settings;
3. current brief;
4. locked evidence;
5. relevant MOTGU knowledge;
6. relevant content memory;
7. limited Golden Examples;
8. task instruction.

Mỗi context item phải giữ provenance ID khi có.

## 10. Học từ OpenHuman — phần áp dụng

Áp dụng nguyên lý:

- canonicalize trước khi memory;
- deterministic IDs/fingerprints;
- source/topic/global-style summaries chỉ khi data scale cần;
- provenance xuyên suốt;
- checkpointed durable runs;
- bounded context;
- budget/cost telemetry;
- post-run learning;
- approval gates.

Không áp dụng V1:

- personal assistant shell;
- messaging channels;
- generic agent teams;
- arbitrary workflow platform;
- desktop local-first app;
- auto-fetch hàng trăm integrations.

## 11. Failure design

Mọi external call phải có:

- timeout;
- retry policy có giới hạn;
- classification retryable/non-retryable;
- error payload đã làm sạch secret;
- circuit break hoặc fail-fast khi provider lỗi lặp;
- user-visible root cause ở run state.

Không retry vô hạn.

## 12. Security

- secrets chỉ ở secret manager/environment, không lưu plaintext trong run artifacts;
- sanitize prompt/tool logs trước khi hiển thị/export;
- publishing credential có quyền tối thiểu;
- external research content được coi là untrusted input;
- không cho retrieved content tự ghi đè system rules/settings.

## 13. API contract

API chỉ expose resource/state rõ ràng, ví dụ:

```text
POST   /projects/{project_id}/content-runs
GET    /content-runs/{run_id}
POST   /content-runs/{run_id}/actions/approve
POST   /content-runs/{run_id}/actions/retry
POST   /content-runs/{run_id}/actions/cancel
GET    /content-runs/{run_id}/artifacts
GET    /content-runs/{run_id}/evidence
```

Không tạo một endpoint kiểu `/generate-all` đồng bộ cho production.

## 14. Definition of architectural done

Architecture V1 chỉ được coi là khóa khi:

- module ownership rõ;
- state machine rõ;
- source-of-truth rõ;
- data contracts cốt lõi rõ;
- approval points rõ;
- failure/retry/idempotency rõ;
- observability rõ;
- test strategy và regression strategy rõ.
