# PLAN — CONTENTENGINE V1

## Contract update — PR #5 before real-seed Gate B

Planning center: Signal → NeedHypothesis → Opportunity Map → human selection → content
→ ContentExperiment → measured observations → reviewed hypothesis changes.
PR-B upgrades Jina structured provenance/links/token budget; no new provider.
PR-C is **Opportunity Map Mini**, including the existing Keyword/Question Map tool.
CE02 implements Signal/NeedHypothesis/ContentOpportunity/ContentExperiment, replacing
legacy ProblemDesire/AudienceSignal before persistence. Existing keyword tasks below
are substeps, not a separate customer-truth pipeline. Real seed is a founder-proposed
need hypothesis. CI must pass before the bounded live Gate B run; merge stays gated.

## Nguyên tắc lộ trình

Không xây toàn bộ máy rồi mới kiểm tra bài viết có tốt hay không.

Lộ trình V1 dùng hai đường song song:

```text
A. Chứng minh chất lượng nội dung thật sớm
B. Tự động hóa và làm hệ thống bền dần từng lớp
```

Mỗi phase chỉ thêm những viên cần cho phase kế tiếp.

Research/Keyword Plan phải phục vụ trực tiếp một bài thật; không được biến thành dự án SEO riêng trước Golden Journal.

---

## CE00 — Foundation Contracts

Mục tiêu: khóa sản phẩm và kiến trúc trước code.

Status: **CLOSED**.

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
- implementation task map;
- consistency review.

Exit gate đã đạt:

- content identity/version rõ;
- song ngữ ContentCase/LocaleVariant rõ;
- EvidenceSet/Assertion Audit rõ;
- settings source of truth rõ;
- worker/retry/idempotency rõ;
- quality tối thiểu xuất hiện trước Journal đầu tiên;
- Walking Skeleton nằm trong CE01.

---

## CE01 — Repository Skeleton + Research Spike + Walking Skeleton

Mục tiêu: repo chạy được và tạo **một Journal MOTGU thật ở mức thử nghiệm** càng sớm càng tốt.

### A. Hạ tầng tối thiểu

- backend FastAPI skeleton;
- frontend Next.js shell tối thiểu;
- PostgreSQL + migrations;
- module boundaries;
- config loader;
- health endpoints;
- test/lint/build/CI cơ bản.

### B. Research/Search spike tối thiểu

Không làm full CE04 ở đây.

Chỉ chứng minh đường:

```text
1 seed thật
→ Serper discovery
→ Tavily/Exa khi Google nhiều sales/SEO noise
→ chọn vài URL tốt
→ Jina đọc selected URLs
→ structured Discovery Report
```

Default stack:

- Serper = Google/PAA/Related/Autocomplete/organic discovery;
- Tavily = source discovery;
- Exa = semantic/second-hop discovery;
- Jina = selected URL reader;
- Brave = optional fallback, chưa cần build nếu chưa có use case.

Manual ChatGPT/Gemini Deep Research được phép dùng cho topic khó và nhập lại dưới dạng research artifact + source URLs.

### C. Opportunity Map Mini

Từ founder-proposed NeedHypothesis và các signals thật tạo:

```text
MARKET / SEARCH / MOTGU Signal
→ normalize + provenance + dedupe/repost grouping
→ NeedHypothesis + support/contradiction/alternatives/gaps
→ Keyword/Question Map
→ problem / intent classification
→ simple topic clusters
→ pillar / cluster suggestions
→ niche candidates
→ CREATE / UPDATE / MERGE / DO_NOT_WRITE
→ human chọn 1 opportunity
```

Không cần:

- keyword-volume database;
- paid difficulty score;
- backlink analysis;
- crawl competitor lớn;
- auto content calendar.

### D. Editorial calibration tối thiểu

- 3–5 positive excerpts cho locale được thử;
- 3–5 negative excerpts;
- human review rubric;
- một ContentCase thật từ opportunity được chọn;
- một LocaleVariant thật;
- selected/manual EvidenceSet;
- Manual OriginalityPack.

### E. Walking Skeleton

```text
NeedHypothesis + traceable Signals
→ Opportunity Map Mini
→ Human chọn opportunity
→ ContentCase / LocaleVariant
→ EvidenceSet + OriginalityPack
→ Angle
→ Outline
→ Draft
→ Basic Assertion Audit
→ Human Review
```

Chưa cần:

- Content Memory thông minh;
- WordPress publish;
- durable worker hoàn chỉnh;
- multi-project;
- full automatic research orchestration.

Exit gate:

1. repo build/test sạch;
2. một seed thật tạo được Keyword Plan dễ hiểu;
3. human chọn được ít nhất một opportunity có lý do rõ;
4. selected sources tốt hơn việc lấy mặc định top 1–5 Google;
5. một Journal thật được tạo từ dữ liệu thật;
6. người duyệt xác định rõ bài có đáng tiếp tục phát triển không;
7. các lỗi research/content contract được ghi lại trước khi tự động hóa thêm.

Nếu chất lượng chưa đạt, sửa Research/Content/Settings/Quality contract trước khi sang CE02.

---

## CE02 — Core Data + Settings

Mục tiêu: biến dữ liệu thử nghiệm CE01 thành dữ liệu có cấu trúc/version.

Deliverables:

- Project;
- ContentCase;
- LocaleVariant;
- ContentItem/ContentVersion;
- versioned Settings + immutable SettingsSnapshot;
- Prompt/Recipe Registry;
- Brand/Language DNA;
- Editorial Calibration Pack storage;
- Source/SourceDocument;
- Entity/Claim/Evidence/EvidenceSet;
- OriginalityPack;
- MediaAsset/MediaObservation;
- ContentRun/StepRun/Artifact/Approval;
- ContextManifest;
- ModelCall/ToolCall;
- QualityEvaluation;
- structured Research artifacts;
- Keyword Plan artifact/version contract.

Exit gate:

- core data create/read/version được;
- run giữ settings snapshot bất biến;
- ContextManifest tái hiện được input quan trọng;
- vi/en chia sẻ ContentCase nhưng có LocaleVariant riêng;
- research/keyword artifacts giữ source refs và locale.

---

## CE03 — Durable Harness

Mục tiêu: workflow chạy bền, dừng rồi tiếp tục được, không làm trùng việc ngoài hệ thống.

Deliverables:

- run state machine;
- durable job queue;
- worker claim/lease/heartbeat;
- checkpoints;
- retry/error classes;
- approval pause/resume;
- budgets;
- model router/tool adapter;
- telemetry;
- outbox/reconciliation cho side effect;
- restart/resume tests;
- replay/eval mode.

Exit gate:

- synthetic workflow survive restart;
- expired worker lease được lấy lại an toàn;
- bounded retry;
- no duplicate side effects;
- biết chính xác model đã nhận context nào.

---

## CE04 — Knowledge + Production Research

Mục tiêu: nâng Research Spike CE01 thành workflow có thể chạy lặp lại, giữ provenance và tái sử dụng knowledge.

Deliverables:

- source ingest;
- fingerprint/dedupe;
- canonical text/Markdown;
- chunking;
- entity refs;
- retrieval;
- provider routing/budget/fallback production;
- Discovery Research workflow;
- Keyword Plan workflow;
- Evidence Research workflow;
- source selection + commercial-bias/authority metadata;
- second-hop research;
- authority rules;
- Claim/Evidence ledger;
- EvidenceSet lock;
- OriginalityPack builder;
- Knowledge Candidate extraction;
- candidate/approved admission;
- Obsidian mirror/export;
- memory gap report;
- basic contradiction handling.

Exit gate:

- same source ingest twice no duplicate;
- retrieved item có provenance;
- Discovery output không bị dùng nhầm làm factual evidence;
- unsupported claim detectable;
- EvidenceSet bất biến sau lock;
- raw SERP/API payload không làm bẩn Obsidian;
- một research run có thể giải thích provider nào được gọi và vì sao;
- Keyword Plan giữ được nguồn signal cho từng opportunity.

---

## CE05 — Journal Engine V1

Mục tiêu: nâng Walking Skeleton thành workflow Journal dùng được lặp lại.

Deliverables:

- ContentCase/LocaleVariant UI;
- memory overlap check stub;
- research workflows;
- opportunity selection handoff;
- angle generation/approval;
- outline;
- draft;
- bounded review/revise;
- independent `vi-VN`/`en` writers;
- assertion audit;
- final package;
- basic source-copy check.

Exit gate:

- ít nhất một Journal thật chạy end-to-end tới final approval;
- zero critical unsupported assertion;
- human review đạt chuẩn tối thiểu đã đặt ở CE01.

---

## CE06 — Full Quality + Golden Regression

Mục tiêu: biến đánh giá thủ công ban đầu thành hệ thống so sánh và chống đi lùi.

Deliverables:

- deterministic quality checks;
- model-based evaluators;
- human evaluation UI;
- source-copy evaluator;
- Golden/Weak fixtures;
- pairwise regression runner;
- candidate vs baseline report.

Exit gate:

- model/prompt/settings candidate không promote nếu chưa có regression report;
- hard fact gates không phụ thuộc hoàn toàn vào model judge;
- Golden Set có human approval.

---

## CE07 — Artwork Engine V1

Mục tiêu: tạo Artwork content chính xác, giàu giá trị riêng và có căn cứ từ ảnh/dữ liệu thật.

Deliverables:

- WordPress/WooCommerce canonical Artwork adapter;
- artwork fact lock;
- MediaAsset/MediaObservation flow;
- artist context retrieval;
- artist-intent provenance rule;
- bilingual output;
- assertion audit;
- related content/link package.

Exit gate:

- một Artwork thật chạy end-to-end;
- zero canonical fact drift;
- mọi mô tả hình ảnh quan trọng map được về media evidence.

---

## CE08 — WordPress Draft + Measurement Foundation

Mục tiêu: đưa bài sang web an toàn và chuẩn bị đo kết quả.

Deliverables:

- WordPress draft adapter;
- ContentItem ↔ WordPress mapping;
- ContentVersion publish history;
- idempotency/outbox/reconciliation;
- Search Console import;
- Analytics import;
- normalized core metrics;
- Rank Math technical signal spike nếu truy cập ổn định;
- hypothesis mapping.

Exit gate:

- Journal + Artwork tạo draft WordPress an toàn;
- retry không tạo duplicate;
- metrics trace về ContentCase/LocaleVariant/content hypothesis.

---

## CE09 — Content Memory + Learning Loop

Mục tiêu: dùng kho bài và dữ liệu thật để tránh trùng, tìm pattern và học có kiểm soát.

Deliverables:

- ContentItem/Version memory;
- duplicate/intent overlap detector;
- update/refresh/merge/do-not-write recommendation;
- human edit delta;
- learning candidates;
- audience signals;
- minimum-evidence rules;
- 1/3/6-month review reports.

Exit gate:

- system giải thích được học gì và dựa trên dữ liệu nào;
- biết khi nào dữ liệu chưa đủ;
- không tự đổi production settings.

---

## CE10 — Production Pilot

Run 10–20 content hypotheses có chủ đích.

Mục tiêu:

- kiểm chứng quality process;
- tìm failure modes;
- tune cost;
- tune human approval load;
- establish first stable Golden Set;
- collect first real audience signals;
- quyết định nên đào sâu ngách nào.

Không mở CRM/Sales Agent trước CE10 review.

---

## Thứ tự ưu tiên nếu phải cắt scope

Giữ trước:

1. chất lượng một bài thật;
2. audience/problem đúng;
3. source/evidence đúng;
4. MOTGU originality;
5. human approval;
6. content identity/version;
7. reproducibility;
8. durable run;
9. measurement/learning.

Hoãn trước:

1. multi-project UI;
2. generic workflow builder;
3. full Memory Tree;
4. nhiều integrations;
5. Brave/default extra providers khi chưa có use case;
6. keyword volume/backlink suite;
7. nhiều model/provider chỉ để có lựa chọn;
8. automation publish hoàn toàn.
