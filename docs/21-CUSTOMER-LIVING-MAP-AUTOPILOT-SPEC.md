# 21 — CUSTOMER LIVING MAP & CONTROLLED AUTOPILOT SPEC

## 1. Mục tiêu

ContentEngine phải trở thành hệ thống hiểu khách hàng và vận hành nội dung ngày càng tốt hơn, không chỉ là máy tạo bài.

North Star:

```text
Deep Research
→ Raw Sources
→ Signal
→ Customer Insight
→ Customer Living Map
   ├─ Audience
   ├─ Needs
   └─ Journey
→ Content Coverage
→ Content Opportunity
→ Lens Selection
→ Evidence / Originality
→ Angle → Outline → Writer
→ Reader Value Gate
→ SEO / AI Readiness
→ Publish
→ Search / Behaviour / Sales
→ Signal mới
→ Customer Map Update
```

Mục tiêu vận hành: tự động hóa phần lớn việc thực thi, nhưng không tự động hóa quyền thay đổi luật, prompt, workflow hoặc chiến lược production.

## 2. Luật dữ liệu

Phải giữ bốn tầng riêng:

```text
Raw Source
→ Signal: ta thực sự quan sát gì?
→ Customer Insight: điều này có thể cho thấy gì?
→ Hypothesis / Living Map: hiểu biết đang được kiểm chứng
```

Không được:
- biến một quan sát thành kết luận;
- biến model interpretation thành customer truth;
- đếm repost là nhiều nguồn độc lập;
- overwrite lịch sử cũ khi hiểu biết thay đổi.

Mỗi insight/hypothesis phải giữ support, contradiction, alternative explanations, missing evidence và provenance.

## 3. Customer Insight

Các loại ban đầu:

- job
- pain
- desire
- question
- fear
- objection
- barrier
- trigger
- decision_factor
- trust_builder
- trust_breaker
- language
- behaviour
- expectation
- post_purchase_need
- referral_trigger
- repeat_purchase_trigger

Một Insight có thể có nhiều Signal; Signal có thể supports, contradicts hoặc context-only.

## 4. Customer Living Map

Living Map không phải persona tĩnh.

Mỗi audience cần nhìn được:
- hoàn cảnh;
- mục tiêu;
- needs;
- wants;
- fears;
- questions;
- barriers;
- decision factors;
- trust builders / trust breakers;
- language;
- behaviour;
- post-purchase needs;
- referral / repeat-purchase triggers.

Journey mặc định để quan sát:

```text
Chưa biết
→ Biết
→ Quan tâm
→ Thích
→ Tin
→ Mua
→ Hài lòng
→ Giới thiệu
→ Mua tiếp
```

Journey không phải đường đi bắt buộc.

## 5. Derived views

Không tạo nhiều truth store song song.

Từ cùng dữ liệu gốc có thể sinh:
- Value Proposition Canvas — Customer Profile;
- Question / Keyword Map;
- JTBD Map;
- Journey Map;
- Topic Map;
- Content planning views.

Value Map của MOTGU là giả thuyết chiến lược, không phải customer truth.

## 6. Content Coverage

Mỗi ContentItem cần map được tới:
- một primary Need;
- zero hoặc nhiều supporting Needs;
- Topic;
- Intent;
- Journey stage hỗ trợ;
- trạng thái nội dung;
- evidence/originality lineage;
- performance observations khi có.

Coverage status tối thiểu:
- MISSING
- PLANNED
- IN_PROGRESS
- PUBLISHED
- NEEDS_UPDATE
- WEAK
- WORKING
- INSUFFICIENT_DATA

Không dùng điểm tổng giả chính xác.

## 7. Content Opportunity và 7 Content Lenses

Topic, Intent và Lens là ba trục riêng.

Bảy Lens:
- DEFINITION
- MISCONCEPTION
- SIGNALS
- CAUSES
- METHOD
- CASE
- POV

Lens là công cụ chọn cách khai thác, không phải bước bắt buộc sinh thêm bài.

Mỗi candidate cần:
- reader_need;
- added_value;
- evidence_needed;
- evidence_available;
- speaking_authority;
- existing_coverage;
- guards;
- reasons;
- source refs.

Quyết định:
- SELECT
- MERGE
- HOLD
- DROP

Điều kiện:
- CASE cần case thật + provenance + quyền dùng;
- POV cần MOTGU position được xác nhận;
- SIGNALS không được biến dấu hiệu thành kết luận;
- CAUSES không được nâng correlation thành causality;
- thiếu evidence thì HOLD.

V1 lưu Lens Selection dưới dạng versioned Artifact trước khi tạo schema riêng.

## 8. Reader Value trước SEO/AI

### Reader Value Gate

Kiểm tra:
- đúng audience;
- đúng need/situation;
- trả lời primary question;
- reader_before → reader_after;
- actionable/useful;
- không filler/generic AI;
- có originality thật;
- claims chính có evidence;
- CTA hữu ích, không ép bán.

Reader Value fail thì không publish dù SEO/AI readiness pass.

### SEO / AI Readiness

Kiểm tra:
- intent;
- title/H1;
- answer passage;
- heading;
- entity clarity;
- internal links;
- source/citation clarity;
- metadata;
- structured data phù hợp;
- canonical/indexability;
- freshness;
- image alt/caption khi có;
- không keyword stuffing;
- không FAQ giả.

## 9. Controlled Autopilot

### 9.1 Control Plane

Control Plane chọn safe next task từ canonical state + policy.

Harness vẫn sở hữu:
- durable run/job;
- lease/heartbeat;
- retry;
- budget;
- checkpoint;
- approval pause/resume;
- idempotency;
- reconciliation.

Không tạo workflow engine thứ hai.

### 9.2 ExecutionPlan

Mỗi task tự động phải có:
- goal;
- exact inputs;
- expected outputs;
- allowed actions;
- forbidden actions;
- allowed tools;
- budget;
- timeout;
- max attempts;
- stop conditions;
- required checks;
- reviewer;
- next action on pass/fail;
- human gate requirement.

V1 ưu tiên immutable Artifact + SettingsSnapshot.

### 9.3 Capability policy

Quyền tối thiểu:
- READ
- WRITE_ARTIFACT
- RUN_MODEL
- RUN_TOOL
- RESEARCH_EXTERNAL
- WRITE_DATABASE
- PUBLISH
- CHANGE_SETTINGS
- CHANGE_PROMPT
- CHANGE_WORKFLOW

Least privilege, fail closed nếu mismatch.

### 9.4 Agent bridge

ContentEngine không phụ thuộc chặt vào một app.

Bridge semantics tối thiểu:
- claim task;
- heartbeat;
- complete;
- fail;
- return artifact refs + safe telemetry.

Coordinator mặc định hiện tại là packaged Codex runtime trong ChatGPT. Antigravity chỉ được kích hoạt bằng adapter/policy đã review và task riêng.

### 9.5 Independent review

Không dùng:
`worker → tự chấm → tự PASS`.

Dùng:
```text
Worker output
→ deterministic checks
→ independent review khi cần judgement
→ Harness gate
→ next task
```

## 10. Human 1%

Human-by-exception cho:
- research;
- extraction;
- dedupe;
- map refresh;
- coverage;
- candidate planning;
- evidence gathering;
- draft/revision;
- checks;
- measurement;
- learning candidate generation.

Các gate hiện hành vẫn giữ cho tới khi có contract change riêng:
- Angle approval;
- Outline approval;
- final content approval;
- publish authorization riêng.

## 11. Measurement và learning

Measurement identity phải truy được:

```text
PublishedContent
→ ContentVersion
→ ContentItem
→ ContentCase
→ ContentOpportunity
→ NeedHypothesis
→ Audience
→ Journey
→ Lens Selection
```

Search/behaviour/sales chỉ tạo observation/Signal, không tự suy ra trust hoặc causality.

Learning:

```text
Observation
→ LearningCandidate
→ gather evidence
→ human review
→ experiment
→ regression
→ promote / reject / archive
```

Không tự sửa prompt/settings/workflow production từ một bài thắng/thua.

## 12. Daily refresh

Không deep-research toàn Internet mỗi ngày.

Daily refresh ưu tiên:
- internal signals;
- Search Console;
- website behaviour;
- inquiry;
- conversion;
- new/updated content;
- manual observations;
- dedupe;
- Customer Map refresh;
- Coverage refresh;
- change report;
- priority refresh.

External Deep Research chỉ chạy khi:
- có Need mới;
- thiếu evidence;
- thông tin có dấu hiệu thay đổi;
- opportunity quan trọng cần xác minh;
- content cũ cần refresh;
- human yêu cầu.

Mỗi refresh phải trả “what changed”, không chỉ số record tăng.

## 13. UI / UX

Navigation mục tiêu:
1. Overview
2. Customers
3. Content Map
4. Production
5. Needs Me
6. Learning
7. System

Dashboard business và Control Center là hai lớp khác nhau.

Backend cung cấp read model; frontend không tự suy luận truth.

API mục tiêu ban đầu:
- GET /customer-map/summary
- GET /customer-map/audiences/{id}
- GET /content-coverage
- GET /customer-map/changes
- GET /priorities
- GET /control-center
- GET /needs-me

Mọi quyết định tự động quan trọng phải có “Why?” với reasons + source refs.

## 14. Kế hoạch thực thi

### ARCH-21 — Contract sync

- [x] Chốt spec này.
- [x] Đồng bộ PLAN/TASKS/CHECKLIST/AI_context trong cùng PR.
- [ ] Founder merge PR.
- [ ] Không chạy migration/model/runtime trong slice này.

Exit: GitHub là nguồn kế hoạch chuẩn.

### CT-01 — CustomerInsight foundation

- [ ] Tạo CustomerInsight model/contract.
- [ ] Tạo CustomerInsight ↔ Signal relation.
- [ ] supports / contradicts / context.
- [ ] taxonomy ban đầu.
- [ ] provenance + version.
- [ ] missing evidence + alternatives.
- [ ] dedupe rules.
- [ ] migration.
- [ ] unit tests.
- [ ] persistence tests.
- [ ] replay/idempotency tests.
- [ ] không đổi Journal Angle/Outline/Writer.
- [ ] local migration cần Founder authorization riêng.

Exit: từ Signal có thể persist Insight sạch, có truy nguyên và phản bác.

### AU-01 — ExecutionPlan + capability policy

- [ ] immutable ExecutionPlan Artifact.
- [ ] exact input/output contract.
- [ ] allowed/forbidden actions.
- [ ] allowed tools.
- [ ] max attempts.
- [ ] timeout.
- [ ] budget.
- [ ] stop conditions.
- [ ] reviewer.
- [ ] versioned capability policy.
- [ ] mismatch fails closed.
- [ ] stale/duplicate/replay tests.

Exit: backend biết chính xác worker được làm gì trước khi giao task.

### CM-01 — Customer Living Map

- [ ] Audience view.
- [ ] Need view.
- [ ] Journey config.
- [ ] CustomerMapSnapshot Artifact.
- [ ] incremental refresh.
- [ ] NEW/SUPPORT/CONTRADICT/DUPLICATE change report.
- [ ] read APIs.
- [ ] tests không cần research lại toàn bộ.

Exit: hỏi một audience/need là thấy evidence, contradictions, gaps và recent changes.

### CC-01 — Content Coverage

- [ ] primary/supporting Need links.
- [ ] ContentItem ↔ Journey.
- [ ] coverage statuses.
- [ ] missing/weak/update/duplicate detection.
- [ ] read API.
- [ ] không áp dụng “1 need = 1 article”.

Exit: backend trả lời được vấn đề nào đã/đang/chưa được giải quyết.

### LS-01 — Lens Selection

- [ ] 7 Lens candidate Artifact.
- [ ] SELECT/MERGE/HOLD/DROP.
- [ ] CASE/POV/SIGNALS/CAUSES guards.
- [ ] input từ Customer Map + Coverage.
- [ ] output đi vào Evidence/Angle context.
- [ ] regression chứng minh không ép 7 bài.

Exit: loại góc yếu và cải thiện Angle mà không tạo content rác.

### AU-02 — Agent Bridge + auto-next orchestration

- [ ] local bridge claim/heartbeat/complete/fail.
- [ ] exact plan/settings/task/worker binding.
- [ ] subagent telemetry.
- [ ] auto-next chỉ khi canonical state rõ.
- [ ] independent reviewer route.
- [ ] recovery/retry/idempotency.
- [ ] Antigravity adapter chỉ khi task riêng được mở.

Exit: một approved plan có thể tự chạy nhiều bước an toàn mà Founder không điều khiển từng command.

### QA-01 — Reader Value + SEO/AI Readiness

- [ ] Reader Value evaluator.
- [ ] hard routing.
- [ ] SEO/AI readiness riêng.
- [ ] không có overall score override hard gate.
- [ ] pairwise regression.
- [ ] UI findings đơn giản.

Exit: content tốt cho người đọc là điều kiện trước discovery optimization.

### PM-01 — Publish + measurement identity

- [ ] safe publish package.
- [ ] idempotent WordPress handoff/draft/publish.
- [ ] reconcile ambiguous external effects.
- [ ] URL/external ID mapping.
- [ ] Search Console observations.
- [ ] Analytics observations.
- [ ] conversion observations.
- [ ] map metrics về Audience/Need/Journey/Lens.
- [ ] INSUFFICIENT_DATA.

Exit: observation/conversion truy ngược được về content hypothesis và customer context.

### LL-01 — Closed learning loop

- [ ] behaviour/search/sales → Signal.
- [ ] LearningCandidate lifecycle.
- [ ] minimum evidence.
- [ ] alternatives/negative evidence.
- [ ] baseline-vs-candidate.
- [ ] regression.
- [ ] rollback.
- [ ] no silent auto-promotion.

Exit: hệ thống học được mà không tự củng cố lỗi.

### UX-01 — Control Center + Living Map UI

- [ ] Overview.
- [ ] Customers.
- [ ] Content Map.
- [ ] Production.
- [ ] Needs Me.
- [ ] Learning.
- [ ] System.
- [ ] Daily Digest.
- [ ] Blocked/Recovery UX.
- [ ] Why? details.
- [ ] technical telemetry ở Advanced details.

Exit: Founder quản lý bằng exception, không theo dõi từng run.

### E2E-01 — Real closed-loop pilot

- [ ] Deep Research → Signal → Insight.
- [ ] Map + Coverage.
- [ ] Opportunity + Lens.
- [ ] Evidence → Angle → Outline → Writer.
- [ ] Reader Value + SEO/AI.
- [ ] publish có authorization.
- [ ] measure.
- [ ] signal quay lại map.
- [ ] dashboard phản ánh change.
- [ ] no case-specific bypass.
- [ ] safe restart/replay.
- [ ] Founder chỉ thực hiện các gate được quy định.

Exit: một case thật chạy vòng kín.

## 15. Thứ tự thực thi và WIP

Thứ tự mặc định:

```text
ARCH-21
→ CT-01
→ AU-01
→ CM-01
→ CC-01
→ LS-01
→ AU-02
→ QA-01
→ PM-01
→ LL-01
→ UX-01
→ E2E-01
```

WIP:
- một implementation;
- một verification liên quan.

Không interleave migration/runtime mutation của track mới vào một active F7 content execution.

## 16. Definition of Done toàn kiến trúc

Chỉ coi hoàn thành khi một case thật chứng minh:

```text
Deep Research
→ Raw Source
→ Signal
→ Customer Insight
→ Customer Living Map
→ Content Coverage
→ Content Opportunity
→ Lens
→ Evidence / Originality
→ Angle
→ Outline
→ Writer
→ Reader Value + SEO/AI
→ Publish
→ Search / Behaviour / Sales
→ Signal mới
→ Customer Map Update
```

và:
- mọi bước truy nguyên được;
- không silent truth promotion;
- automation policy rõ;
- retry/recovery không nhân đôi side effects;
- UI chỉ hiện canonical state;
- Founder chỉ xử lý exception/gate;
- learning quan trọng có evidence + regression + rollback.
