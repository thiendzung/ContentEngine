# 02 — ARCHITECTURE SPEC

## 1. Mục tiêu kiến trúc

Kiến trúc phải phục vụ một việc trước tiên: tạo Journal và Artwork content chất lượng cao cho MOTGU, có thể kiểm tra, đo, học và cải thiện theo thời gian.

Không tối ưu cho độ tổng quát tối đa ở V1.

Nguyên tắc quan trọng:

> Kiểm chứng chất lượng nội dung thật càng sớm càng tốt, rồi mới tự động hóa từng phần.

## 2. Kiến trúc logic

```text
Configuration
    ↓
Content Case + Locale Variant
    ↓
Knowledge Recall
    ↓
Discovery Research
    ↓
Keyword / Question / Opportunity Map
    ↓
Evidence Research
    ↓
Evidence Set + Originality Pack
    ↓
Context Builder + Context Manifest
    ↓
Durable Run Harness
    ↓
Journal / Artwork Workflow
    ↓
Assertion Audit + Quality + Human Approval
    ↓
Content Item + Version
    ↓
WordPress Draft/Publish
    ↓
Measurement
    ↓
Learning Candidate
```

## 3. Các module chính

### `system`

Sở hữu:

- project settings;
- prompt/recipe registry;
- model/provider configuration;
- secrets references;
- feature flags;
- versioned configuration;
- immutable settings snapshot.

Không sở hữu content workflow business logic.

### `knowledge`

Sở hữu:

- source registry;
- source ingest;
- canonical document representation;
- fingerprints/dedupe;
- chunks;
- entities;
- claims/evidence;
- evidence sets;
- media evidence;
- retrieval;
- content memory index;
- approved/candidate knowledge state;
- Obsidian mirror/export contract.

`knowledge` không quyết định query nào đáng viết thành bài.

### `research`

Sở hữu research workflow và provider adapters:

- Discovery Research;
- Evidence Research;
- Search provider routing;
- source discovery;
- second-hop research;
- source selection metadata;
- Keyword Plan mini;
- Knowledge Candidate extraction handoff.

Cấu trúc logic:

```text
research/
├── discovery/
├── evidence/
├── keyword_plan/
├── knowledge_ingest/
└── providers/
    ├── serper
    ├── tavily
    ├── exa
    ├── jina
    └── brave_optional
```

Default provider roles được khóa ở `docs/11-RESEARCH-SEARCH-SPEC.md`.

`research` không được coi search position là authority và không tự promote Knowledge Candidate thành truth.

### `harness`

Sở hữu:

- Run/StepRun;
- state machine;
- durable job queue/claim;
- checkpoints;
- worker lease/heartbeat/recovery;
- resume/retry;
- budgets;
- model/tool telemetry;
- approval pause/resume;
- cancellation;
- side-effect idempotency/reconciliation.

Harness không sở hữu Journal/Artwork prompts hoặc search strategy business rule.

### `content_engine`

Sở hữu:

- ContentCase/LocaleVariant orchestration;
- Evidence selection handoff;
- Originality Pack;
- Angle;
- Outline;
- Draft;
- Review;
- Final package.

`content_engine` gọi `research` qua contract, không tự viết provider-specific search code.

Bên trong chia `journal` và `artwork` theo vertical slice khi logic khác nhau.

### `evals`

Sở hữu:

- deterministic checks;
- model-based evaluators;
- human evaluation contract;
- assertion audit;
- evidence/factual checks;
- brand voice;
- usefulness;
- originality;
- structure/readability;
- search/AI readability;
- source-copy/phrase-overlap checks;
- regression/pairwise comparison.

Evaluator không tự publish.

### `learning`

Sở hữu:

- human edit deltas;
- content performance observations;
- audience signals;
- learning candidates;
- approved learnings;
- experiments;
- Golden/Weak Set metadata;
- minimum-evidence rules trước khi kết luận.

### `publishing`

Sở hữu WordPress adapter và publish history.

V1 ưu tiên draft/handoff an toàn trước full auto-publish.

### `measurement`

Sở hữu normalized metrics từ:

- Search Console;
- Analytics;
- Rank Math/WordPress technical checks khi có đường truy cập ổn định;
- MOTGU-defined conversion events.

Measurement chỉ cung cấp signal, không tự thay đổi strategy.

## 4. Search provider contract V1

Default stack:

```text
SERPER
→ Google PAA / Related / Autocomplete / organic discovery

TAVILY
→ source discovery khi SERP nhiều sales/SEO noise

EXA
→ semantic / second-hop source discovery

JINA
→ đọc sạch selected URL

BRAVE
→ optional fallback / coverage check
```

Không gọi tất cả provider cho mọi query.

Flow mặc định:

```text
Knowledge Recall
→ Serper
→ đủ signal thì dừng mở rộng
→ Tavily nếu cần nguồn tốt hơn
→ Exa nếu cần nguồn sâu/second-hop
→ source selection
→ Jina read
```

Search provider trả signal/source candidate. Authority được xử lý theo Research/Evidence contract, không theo rank.

## 5. Keyword Plan mini boundary

`keyword_plan` là một mini module bên trong `research`, không phải một SEO suite độc lập.

Nó nhận Discovery signals và tạo:

- normalized questions/queries;
- audience/problem/intent classification;
- topic clusters;
- pillar candidates;
- cluster candidates;
- niche candidates;
- content decision: `CREATE | UPDATE | REFRESH | MERGE | LINK_ONLY | DO_NOT_WRITE`;
- priority: `NOW | NEXT | LATER | NO`.

Không sở hữu:

- paid keyword volume database;
- backlink analysis;
- auto content calendar;
- auto publish.

Contract chi tiết: `docs/12-KEYWORD-PLAN-SPEC.md`.

## 6. Kiến trúc triển khai đề xuất

- Backend: Python + FastAPI;
- Frontend: Next.js + React;
- Production DB: PostgreSQL;
- Local/dev: PostgreSQL ưu tiên; SQLite chỉ dùng khi test nhỏ thực sự có lợi và không che khác biệt production;
- artifact lớn: file/object storage hoặc DB reference;
- WordPress: external canonical publishing target;
- background execution: durable jobs trong DB + worker đơn giản ở V1.

Không đưa Rust/Tauri hoặc generic workflow platform từ OpenHuman vào V1.

Không cần framework graph phức tạp nếu state machine đơn giản đáp ứng đủ checkpoint/resume.

## 7. Repository target structure

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
│   │       ├── research/
│   │       │   ├── discovery/
│   │       │   ├── evidence/
│   │       │   ├── keyword_plan/
│   │       │   ├── knowledge_ingest/
│   │       │   └── providers/
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
├── evals/
│   ├── calibration/
│   ├── golden/
│   ├── weak/
│   └── reports/
└── scripts/
```

## 8. Walking Skeleton — bắt buộc làm sớm

Trước khi hoàn thiện toàn bộ hạ tầng, phải có một đường mỏng dùng dữ liệu thật:

```text
Real MOTGU Seed / Problem
+ Mini Keyword Plan
+ Manual/Selected EvidenceSet
+ Manual OriginalityPack
+ Real Brand/Language Examples
    ↓
Human chọn 1 Content Opportunity
    ↓
Angle
    ↓
Outline
    ↓
Draft
    ↓
Basic Assertion Audit
    ↓
Human Editorial Review
```

Walking Skeleton không cần publish, Content Memory thông minh hoặc full auto research.

Research/Search có thể chạy manual/scripted ở CE01; chưa cần durable worker đầy đủ.

Mục tiêu duy nhất: chứng minh research + content contract có thể tạo một bài đáng đăng.

Nếu không đạt, sửa spec/content logic trước khi mở rộng hạ tầng.

## 9. Durable Run Graph production

```text
CREATE_RUN
  ↓
KNOWLEDGE_RECALL
  ↓
DISCOVERY_RESEARCH
  ↓
KEYWORD_PLAN / OPPORTUNITY_SELECTION
  ↓
EVIDENCE_RESEARCH
  ↓
EVIDENCE_LOCK + ORIGINALITY_PACK
  ↓
ANGLE
  ↓
[HUMAN APPROVAL]
  ↓
OUTLINE
  ↓
[HUMAN APPROVAL configurable]
  ↓
DRAFT
  ↓
REVIEW / REVISE bounded
  ↓
ASSERTION_AUDIT
  ↓
QUALITY_GATE
  ↓
[FINAL HUMAN APPROVAL]
  ↓
CONTENT_VERSION + PACKAGE
  ↓
PUBLISH explicit
  ↓
MEASURE
```

Mỗi node persist output trước state transition.

Keyword Plan có thể được bỏ qua khi ContentCase đã do human xác định trực tiếp và không cần discovery mới.

## 10. Worker model V1

Production run không giữ một HTTP request dài.

```text
API creates/updates durable job
    ↓
Worker claims job with lease
    ↓
Heartbeat while running
    ↓
Persist output + state
    ↓
Commit next job/state
```

Nếu worker chết:

- lease hết hạn;
- job được reclaim;
- system resume từ checkpoint;
- side effect phải reconciliation trước retry.

V1 không cần nhiều worker để chạy; nhưng contract phải an toàn khi có nhiều worker sau này.

## 11. Outbox cho side effect quan trọng

Các side effect như publish nên dùng durable intent/outbox hoặc cơ chế tương đương:

```text
DB records publish intent
→ commit
→ worker executes WordPress call
→ reconcile result
→ mark completed
```

Mục tiêu: service chết giữa chừng không tạo publish mù hoặc publish trùng.

## 12. State tối thiểu

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

Retry history không bị overwrite.

## 13. Content lineage

Một content flow phải phân biệt:

```text
ContentCase
→ LocaleVariant
→ ContentItem
→ ContentVersion
→ PublishedContent
```

`ContentRun.mode` xác định: `create | update | refresh | localize`.

## 14. Context Builder

Thứ tự ưu tiên:

1. system safety/operating rules;
2. approved project/brand settings;
3. current ContentCase + LocaleVariant;
4. locked EvidenceSet;
5. OriginalityPack;
6. relevant MOTGU knowledge;
7. relevant Content Memory;
8. limited Golden Examples;
9. task instruction.

Discovery/Keyword raw signals không được dump toàn bộ vào writer context. Chỉ summary/candidates đã chọn đi tiếp khi cần.

Mỗi model call quan trọng tạo `ContextManifest` để biết chính xác model đã nhìn thấy gì.

## 15. Knowledge / Obsidian boundary

Raw SERP/API payload không đưa vào Obsidian mặc định.

```text
Raw result/page
→ Source/SourceDocument
→ Knowledge Candidate
→ dedupe + provenance + review
→ Approved Knowledge
→ Obsidian mirror nếu hữu ích
```

Obsidian là human-readable workspace/mirror. Một note không tự trở thành canonical truth chỉ vì tồn tại.

## 16. Học từ OpenHuman — phần áp dụng

Áp dụng nguyên lý:

- canonicalize trước memory;
- deterministic IDs/fingerprints;
- provenance xuyên suốt;
- search memory trước external research;
- chỉ external-search phần còn thiếu;
- checkpointed durable runs;
- worker recovery;
- bounded context;
- model/tool budget telemetry;
- post-run learning;
- approval gates;
- summary nhiều tầng chỉ khi corpus đủ lớn.

Không áp dụng V1:

- personal assistant shell;
- messaging channels;
- generic agent teams;
- arbitrary workflow platform;
- desktop local-first app;
- auto-fetch hàng trăm integrations.

## 17. Failure design

Mọi external call phải có:

- timeout;
- retry có giới hạn;
- classification retryable/non-retryable;
- error payload đã làm sạch secret;
- fail-fast/circuit protection khi provider lỗi lặp;
- user-visible root cause;
- reconciliation cho side effect không rõ kết quả;
- explicit provider budget/quota exhaustion.

Research provider fallback phải có giới hạn, không tạo loop gọi nhiều API vô tận.

## 18. Security

- secrets chỉ ở environment/secret manager;
- sanitize prompt/tool logs;
- search API keys không ghi vào artifacts;
- publishing credential có quyền tối thiểu;
- external research content là untrusted input;
- retrieved content không được ghi đè system/settings;
- media rights/status phải được giữ nếu dùng asset để publish.

## 19. API contract

Ví dụ:

```text
POST   /projects/{project_id}/content-cases
POST   /content-cases/{case_id}/locale-variants
POST   /research/discovery-runs
GET    /research/discovery-runs/{run_id}
POST   /research/keyword-plans
GET    /research/keyword-plans/{plan_id}
POST   /locale-variants/{variant_id}/runs
GET    /content-runs/{run_id}
POST   /content-runs/{run_id}/actions/approve
POST   /content-runs/{run_id}/actions/retry
POST   /content-runs/{run_id}/actions/cancel
GET    /content-runs/{run_id}/artifacts
GET    /content-runs/{run_id}/evidence
```

Không có production endpoint `/generate-all` đồng bộ.

## 20. Definition of architectural done

Architecture V1 chỉ được coi là khóa khi:

- module ownership rõ;
- Research vs Knowledge vs ContentEngine boundary rõ;
- default search provider roles rõ;
- Keyword Plan là mini module có scope giới hạn;
- content identity/version rõ;
- state + worker recovery rõ;
- source of truth rõ;
- data contracts cốt lõi rõ;
- EvidenceSet/Assertion Audit rõ;
- approval points rõ;
- failure/retry/idempotency rõ;
- settings/context snapshot rõ;
- test/regression strategy rõ;
- Walking Skeleton được đưa vào roadmap sớm.
