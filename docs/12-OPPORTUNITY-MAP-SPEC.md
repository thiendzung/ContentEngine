# 12 — OPPORTUNITY MAP SPEC

## Contract chính — Opportunity Map Mini

Opportunity Map là đầu ra planning của Research. Keyword/Question Map là công cụ con,
không phải trung tâm quyết định viết bài. Giữ package `research/keyword_plan/` hiện có.

```text
MARKET / SEARCH / MOTGU Signal
→ dedupe + provenance
→ NeedHypothesis
→ support / contradiction / alternative explanations / missing evidence
→ Question Map + existing content check + MOTGU Right-to-Win
→ ContentOpportunity
→ Human Selection
→ Research + approved MOTGU material
→ Journal / Artwork
→ ContentExperiment → Measure → reviewed hypothesis revision
```

Nguồn và trạng thái kiểm chứng là hai trục độc lập:

- source_kind: `MARKET | SEARCH | MOTGU`;
- scope: `market_web | motgu_site | motgu_direct`;
- NeedHypothesis status: `PROPOSED | TESTING | SUPPORTED | REJECTED | INSUFFICIENT_EVIDENCE`.

Search Console là `SEARCH / motgu_site`; PAA là `SEARCH / market_web`;
review gallery khác là `MARKET / market_web`; inquiry là `MOTGU / motgu_direct`.
SUPPORTED không đổi nguồn MARKET thành MOTGU và không có nghĩa đúng với mọi khách.
Founder-proposed hypothesis được phép chưa có signal, nhưng phải ghi rõ missing evidence.

### Hai trục độc lập — Customer Truth vs Content Readiness (QM-02F1R0)

Question Map không được dùng trạng thái Customer Truth như một proxy duy nhất cho việc
có nên thử content hay không.

**Customer Truth confidence** giữ nguyên canonical Need status:

- `PROPOSED`;
- `TESTING`;
- `SUPPORTED`;
- `REJECTED`;
- `INSUFFICIENT_EVIDENCE`.

**Content Readiness** là derived planning/admission state, không phải truth store mới.
QM không tự đổi Need status.

Ma trận tối thiểu:

| Customer Truth | Content Readiness policy |
|---|---|
| `PROPOSED` | có thể đạt `READY_FOR_HUMAN_SELECTION` nếu Question/Search/Coverage/duplicate gates đủ rõ |
| `TESTING` | có thể đạt `READY_FOR_HUMAN_SELECTION` nếu các planning gates đủ rõ |
| `SUPPORTED` | vẫn có thể là `RESEARCH_REQUIRED` nếu Question/Search/Coverage chưa đủ |
| `REJECTED` | luôn `BLOCKED` |
| `INSUFFICIENT_EVIDENCE` | `RESEARCH_REQUIRED`; không materialize content experiment |

Founder Selection là **authorization để thử một content experiment đã qua planning gates**,
không phải bằng chứng làm Need đúng hơn. Founder Selection không được bypass stale,
duplicate/reuse/collision, route/admission hoặc target-lineage guard.

Search/PAA/Related/Autocomplete và organic SERP context là planning/search-language Signals.
Chúng không được tự nâng `PROPOSED/TESTING` thành `SUPPORTED`, không được biến thành
Customer Truth và không phải factual Evidence cho Writer. Evidence/Originality vẫn là
downstream authority sau khi ContentCase được materialize.

#352 (thu thập customer evidence trực tiếp) là Learning/Customer-Truth work bổ trợ,
không còn là prerequisite để Question Map planning tiếp tục. Nếu có dữ liệu thật mới,
nó đi vào canonical Customer Truth theo review riêng; không mở content gate bằng quota phỏng vấn.

### Hợp đồng biên tập của ContentOpportunity

- reader + audience scope;
- situation + need_hypothesis_id;
- question/intent/locale;
- promise / reader transformation;
- MOTGU material refs và gaps;
- existing ContentItem refs;
- what_is_actually_new;
- next_discovery_step (bài khác/entity/Visit, không ép mua);
- decision: `CREATE | UPDATE | REFRESH | MERGE | LINK_ONLY | DO_NOT_WRITE`;
- priority: `NOW | NEXT | LATER | NO` + reasons;
- signal refs / support / contradiction / alternative explanations;
- suggested content_type: `journal | artwork`; pillar/cluster chỉ là role của Journal;
- human selection record.

Mỗi cơ hội phải có giá trị riêng; thay keyword, format hoặc Artist không tự đủ lý do CREATE.
UPDATE/REFRESH/MERGE/LINK_ONLY cần target refs. Không bắt buộc viết pillar trước cluster.
Artist/Visit là entity/link target trong V1, không mở thêm engine sản xuất.

### PR-C output và acceptance

`opportunity_map` versioned artifact gồm signals, need_hypotheses, question_map,
opportunities, research_gaps và human_selection. CE01 dùng JSON/Markdown/manual refs;
CE02 mới persist theo `03-DATA-CONTRACT.md`.

Phải chứng minh: dedupe không đếm repost là nguồn độc lập; observation không biến thành
interpretation; founder hypothesis vẫn PROPOSED khi thiếu evidence; có cả phản bác và
alternative explanations hoặc ghi rõ chưa tìm thấy; mỗi opportunity truy về hypothesis
và signals; non-CREATE có target/reason; human chọn một cơ hội trước ContentCase.
Human selection không tự đổi hypothesis sang SUPPORTED.

Các phần bên dưới là contract của công cụ Keyword/Question Map bên trong Opportunity Map.

### Canonical Question Map read-model boundary — QM-01A / QM-01B

Sau Customer Living Map, Question Map không được tự tạo Customer Need mới. Read model
hiện tại chỉ đọc canonical `NeedHypothesis` và các `SEARCH` Signal đang `supports`
Need đó trong đúng project/locale.

QM-01B thêm classification/clustering như **derived semantics**, không đổi source of truth:

```text
Canonical Need + supporting SEARCH Signals
→ locale-specific Question Map
→ deterministic EN/VI classification
→ answer_job
→ cluster = Need + locale + intent + answer_job
```

Các field classification gồm question type, intent, audience stage, topic, answer job,
confidence, query quality và trạng thái classification. Không re-infer canonical Need type.

- EN và VI được phân loại độc lập; không dịch EN sang VI.
- Query off-scope/unresolved vẫn được giữ để truy nguyên nhưng không được vào cluster.
- Locale chưa hỗ trợ hoặc ngôn ngữ không đủ chắc chắn phải `unresolved`, không đoán.
- QM-01B không gọi model/provider. `semantic_fallback_required` chỉ là cờ để giữ biên
  fail-closed cho một slice riêng sau này.
- Primary question ưu tiên provenance gần khách hơn, sau đó independent repetition,
  không chọn đơn thuần vì query ngắn.
- Legacy `OpportunityMapService` chưa đổi semantics trong QM-01B.

### Question Map × Content Coverage — QM-01C

QM-01C không tạo thêm một coverage truth store. Nó join hai read model đã có:

```text
Question cluster = Need + locale + intent + answer_job
             +
canonical Content Coverage state
             ↓
derived cluster coverage
```

Trạng thái cluster:

- `ANSWERED`: có đúng một primary ContentItem phù hợp đang published;
- `STALE`: primary published answer có revision mới chưa publish hoặc là target của
  selected UPDATE/REFRESH;
- `COLLISION`: nhiều primary answers cạnh tranh cùng cluster; khi chưa có item,
  nhiều selected CREATE plans cùng cluster cũng là collision;
- `PARTIAL`: đã có work/plan phù hợp nhưng chưa có primary published answer; published
  content chỉ ở supporting-Need cũng chỉ là partial;
- `MISSING`: không có classified matching content/work/plan;
- `INSUFFICIENT_DATA`: có candidate cùng intent nhưng semantics không đủ chắc để match,
  nên fail closed thay vì kết luận MISSING.

Existing item/opportunity question language được reclassify bằng cùng deterministic v2
classifier chỉ để join. Không thay Need, ContentOpportunity hay Content Coverage authority.
Off-scope/truncated/unresolved không được tính là answered. `GET /question-map` giữ nguyên;
coverage-aware projection dùng endpoint riêng `GET /question-map/coverage`.

### Opportunity Planner v2 — QM-01D

QM-01D biến Question Map + coverage thành recommendation nhưng vẫn chưa tạo
`ContentOpportunity`.

```text
Question cluster
+ coverage
+ canonical Need state
+ linked supporting MOTGU first-party Signals
→ 7 explainable dimensions
→ decision + priority + human-selection readiness
```

Không dùng score 0–100. Bảy chiều bắt buộc:

- Audience Fit: canonical audience binding hoặc `SCOPE_ONLY`;
- Problem Strength: giữ nguyên Need status/type/version;
- Search Evidence: cluster Signal refs + question count;
- Content Gap: trạng thái QM-01C;
- MOTGU Right-to-Win: chỉ linked supporting `MOTGU` Signals;
- Business Connection: derived rule, chưa phải canonical entity binding;
- Evidence Readiness: suy từ canonical Need status, không re-score Need.

Linked supporting MOTGU Signal ở bước này chỉ là first-party planning-relevance evidence.
Nó **không đủ để chứng minh Right-to-Win**. QM-01D vì vậy trả
`right_to_win_proven=false` cho Signal-only state; Signal không phải locked EvidenceSet,
không phải approved OriginalityPack và không mở quyền viết bài.

Decision policy:

- `MISSING → CREATE`;
- `STALE → REFRESH`;
- `ANSWERED → LINK_ONLY` trong QM-01D; linked MOTGU Signal một mình không đủ để
  nâng thành UPDATE;
- `PARTIAL → UPDATE` khi đã có matching **primary** ContentItem; supporting-Need-only
  content không được dùng làm target;
- nếu PARTIAL chỉ có plan thì giữ hướng `CREATE` nhưng readiness là
  `REUSE_EXISTING_PLAN`, không tạo thêm durable plan;
- selected `DO_NOT_WRITE` plan chặn fresh CREATE recommendation;
- `COLLISION → MERGE` khi có nhiều ContentItem; plan-only collision bị BLOCKED
  để không tạo thêm duplicate plan;
- `INSUFFICIENT_DATA → DO_NOT_WRITE / RESEARCH_REQUIRED` ở snapshot hiện tại;
- Need `REJECTED → DO_NOT_WRITE / NO`.

Non-CREATE action dựa trên existing content phải trả explicit ContentItem refs.
Human selection vẫn là bước riêng. Planner không persist recommendation.

Endpoint: `GET /question-map/opportunities`.

### Selected Planner Handoff — QM-02A

QM-02A là write boundary đầu tiên của Question Map v2. Nó không tạo một planner thứ hai.

```text
exact QM-01D planner snapshot
+ one exact READY_FOR_HUMAN_SELECTION cluster
+ Founder/editorial promise
+ 1..12 ordered coverage requirements
+ human selection reason
→ durable ContentOpportunity
→ exactly one durable HumanSelection
```

Reverse boundary:

- không rebuild legacy `OpportunityMapResult` chỉ để gọi persistence cũ;
- không dùng Founder manual intake vì path đó tạo một `founder_manual` Need mới;
- không tạo ContentCase / ContentExperiment trong selection handoff;
- không cho client tự gửi decision/priority/question/intent/target refs.

Canonical mapping:

- Need / reader scope / situation lấy từ exact `NeedHypothesis`;
- question / intent / decision / priority / target refs lấy từ exact planner recommendation;
- promise + ordered coverage commitments là explicit Founder/editorial input;
- signal links chỉ gồm exact supporting SEARCH Signals của cluster trong đúng Need/project/locale;
- `motgu_material_refs_json=[]` ở QM-02A vì Signal-only planner state chưa chứng minh Right-to-Win;
- `what_is_actually_new` phải nói rõ chưa được established thay vì bịa differentiation.

Write gate phải fail closed nếu:

- planner snapshot đã stale trước first persistence;
- cluster không tồn tại/ambiguous;
- readiness khác `READY_FOR_HUMAN_SELECTION`;
- required existing ContentItem target invalid;
- signal lineage không đúng Need/project/locale;
- replay đổi promise / coverage requirements / actor / selection reason.

Idempotency nuance: first persistence làm Content Coverage thay đổi, vì vậy live planner snapshot sau đó
có thể đổi. Exact replay được nhận diện bằng deterministic selection identity từ
`planner_snapshot_hash + cluster_key`; replay hợp lệ trả lại receipt cũ, không ép old planner
snapshot vẫn là current snapshot.

Durable reasons giữ bounded lineage marker tới planner snapshot, planner policy, cluster key và
Question Coverage snapshot. Đây là audit lineage, không phải planner truth store mới.

Endpoint mutation:

`POST /question-map/opportunities/select`

QM-02A không tự chạy Lens/Angle/Writer/Publish.

### Production Decision Router — QM-02B

Sau khi đã có durable ContentOpportunity + HumanSelection, hệ thống không được mặc định rằng
mọi selection đều tạo bài mới.

```text
selected ContentOpportunity
+ exactly one matching HumanSelection
+ exact target ContentItem lineage
→ production route
```

Mapping:

- `CREATE → CREATE_NEW_CONTENT`
- `UPDATE → REVISE_EXISTING_CONTENT`
- `REFRESH → REFRESH_EXISTING_CONTENT`
- `MERGE → RECONCILE_CONTENT`
- `LINK_ONLY → NO_PRODUCTION`
- `DO_NOT_WRITE → STOP`

QM-02B là read-only. Nó chưa tạo ContentCase/ContentVersion/run/job.

Fail-closed rules:

- phải có đúng một durable HumanSelection khớp convenience selection fields;
- CREATE có 0 target;
- UPDATE / REFRESH / LINK_ONLY có đúng 1 target;
- MERGE có ít nhất 2 target;
- DO_NOT_WRITE có 0 target;
- target phải là ContentItem cùng project, cùng locale và có primary ContentCase Need đúng
  với canonical Need của opportunity;
- supporting-Need-only content không được dùng làm production target.

Endpoint:

`GET /question-map/opportunities/{opportunity_id}/route`

Existing Journal CREATE guard vẫn giữ nguyên: `create_or_reuse_journal_case` chỉ nhận
`decision=CREATE`.

### Production Admission Gate — QM-02C

QM-02C consume exact QM-02B route snapshot và chỉ trả lời một câu:

> disposition đã chọn có còn an toàn để materialize ngay lúc này không?

Nó là read-only admission gate, không phải workflow engine.

Input bắt buộc có exact `expected_route_snapshot_hash`. Backend luôn recompute current
QM-02B route trước khi quyết định admission.

Bounded statuses:

- `ADMITTED`;
- `NO_PRODUCTION`;
- `RECONCILIATION_REQUIRED`;
- `BLOCKED_ROUTE_STALE`;
- `BLOCKED_SELECTION_STALE`;
- `BLOCKED_OPPORTUNITY_STALE`;
- `BLOCKED_TARGET_STALE`;
- `BLOCKED_ALREADY_MATERIALIZED`;
- `BLOCKED_PRODUCTION_CONFLICT`.

CREATE chỉ `ADMITTED` khi chưa có ContentCase bind vào selected opportunity.
UPDATE/REFRESH chỉ `ADMITTED` khi exact target lineage không có active
`pending/running/waiting_approval/failed` ContentRun và không có production binding trái contract.
LINK_ONLY/DO_NOT_WRITE không vào production. MERGE đi reconciliation, không vào normal
production admission.

QM-02C không chạy Evidence/Originality. Các gate đó vẫn nằm downstream sau khi có
ContentCase. Không tạo DB row/admission record mới.

Endpoint:

`GET /question-map/opportunities/{opportunity_id}/admission`

Admission response có deterministic snapshot hash nhưng chỉ là read model. QM-02D1 sau này
phải recompute route + admission trong cùng transaction, kiểm tra exact expected hashes rồi
mới materialize CREATE để tránh TOCTOU.

### CREATE Production Handoff — QM-02D1

QM-02D1 là mutation boundary đầu tiên sau Question Map planning và chỉ nhận
`CREATE_NEW_CONTENT`.

Caller phải bind:

- exact QM-02B route snapshot hash;
- exact QM-02C admission snapshot hash;
- idempotency key.

Với request mới, backend dùng cùng một DB transaction để khóa selected ContentOpportunity,
recompute route + Content Readiness, fail closed nếu Need là `REJECTED` hoặc
`INSUFFICIENT_EVIDENCE`, recompute admission, require exact hashes + `ADMITTED`, rồi mới
reuse `create_or_reuse_journal_case` với exact selected/planner lineage.

`PROPOSED | TESTING | SUPPORTED` không tự động được materialize: chúng chỉ có thể đi tiếp
khi exact Question/Search/Coverage/duplicate gates tạo ra
`READY_FOR_HUMAN_SELECTION`, Founder đã chọn đúng candidate, route/admission vẫn current
và D1 recompute lại các guard trong cùng transaction.

**F1R1 implementation:** planner Content Readiness không còn dùng `SUPPORTED` như
điều kiện duy nhất. `PROPOSED | TESTING | SUPPORTED` có thể đạt
`READY_FOR_HUMAN_SELECTION` khi cluster usable, có SEARCH lineage, coverage quyết định được,
không có duplicate/reuse/collision blocker và decision không phải `DO_NOT_WRITE`.
`REJECTED` luôn block; `INSUFFICIENT_EVIDENCE` luôn research-required.

QM-02D1 khóa cả selected opportunity và canonical Need trong cùng transaction. Trước
khi nới truth-status gate, D1 bắt buộc opportunity giữ một **durable QM-02A selection receipt**
hợp lệ: exact contract marker; current planner policy marker; một planner snapshot hash; một
cluster key; một Question Coverage snapshot hash; một selection-payload hash khớp exact
ContentOpportunity bytes; deterministic ContentOpportunity/HumanSelection IDs sinh từ
`planner_snapshot_hash + cluster_key`; đúng một HumanSelection khớp actor/reason/time; và
SEARCH signal lineage hợp lệ. Exact tập Signal đã được Founder chọn còn được bind
bằng `selection_signal_set` hash, và chính tập Signal này cũng nằm trong
`selection_payload` hash. Vì vậy thêm/bớt một SEARCH link hợp lệ sau thời điểm selection
vẫn làm receipt stale và D1 fail closed.

D1 **không recompute live planner snapshot** để chứng minh old selection, vì việc persist
selection tự làm Content Coverage thay đổi và live planner có thể hợp lệ nhưng khác snapshot
đã được Founder chọn. Thay vào đó mutation boundary kiểm tra immutable/deterministic receipt
của đúng QM-02A selection. Marker giả, policy cũ, payload bị sửa, deterministic ID sai,
HumanSelection không khớp hoặc Signal set drift đều fail closed.

D1 chỉ materialize khi current Need thuộc `PROPOSED | TESTING | SUPPORTED`; nếu Need đã
thành `REJECTED` hoặc `INSUFFICIENT_EVIDENCE` thì fail closed. Exact route/admission,
idempotency, replay và downstream Evidence/Originality gates vẫn giữ nguyên.

Output production mới của slice này chỉ gồm:

- đúng một Journal ContentCase;
- đúng một source-locale LocaleVariant;
- một durable OperatorCommand receipt để khóa idempotency/audit.

Không tạo ContentRun/StepRun/Job và không auto-Start. Evidence/Originality vẫn là downstream
authority. UPDATE/REFRESH/MERGE không được đi qua endpoint này.

Endpoint:

`POST /question-map/opportunities/{opportunity_id}/materialize-create`

Exact replay cùng idempotency/request trả receipt cũ mà không materialize lại. Một request
khác dùng cùng idempotency key phải fail closed. Opportunity row lock là concurrency boundary
cho các idempotency key khác nhau cùng nhắm một selected opportunity.

Sau khi QM-02D1 merge phải chạy QM-02F1 early real CREATE pilot trước khi mở D2/D3.

## 1. Mục tiêu

Keyword Plan không phải công cụ gom thật nhiều từ khóa.

Mục tiêu là tạo **bản đồ câu hỏi và cơ hội nội dung** để MOTGU biết:

- khách đang quan tâm điều gì;
- các câu hỏi liên kết với nhau thế nào;
- nên có pillar nào;
- cluster nào hỗ trợ pillar;
- nội dung nào nên viết mới, cập nhật, gộp hoặc không viết;
- ngách nào MOTGU có lợi thế riêng để nói tốt hơn web chung.

Tên module có thể giữ là `keyword_plan`, nhưng tư duy sản phẩm là **Question & Opportunity Map**.

## 2. Không tối ưu theo search volume đơn thuần

V1 không cần một database hàng chục nghìn keyword.

Một cơ hội tốt phải nằm ở giao điểm:

```text
Real Audience Problem
+ Search/Question Signal
+ Weak/Generic Existing Answers
+ MOTGU Originality
+ Useful Business Path
+ Evidence Feasibility
= Content Opportunity
```

Một query nhỏ nhưng rất đúng khách MOTGU có thể đáng làm hơn keyword lớn nhưng chung chung.

## 3. Input

Một Keyword Plan run nhận tối thiểu:

- `project_id`;
- locale;
- seed topic hoặc seed question;
- optional AudienceHypothesis;
- optional NeedHypothesis;
- optional MOTGU entity: Artist/Artwork/Workshop/Visit;
- optional desired action;
- existing Content Memory summary nếu có.

Ví dụ:

```text
locale: en
seed: buy art in Hanoi
audience: first-time-art-buyer
problem: fear-of-choosing-wrong
```

## 4. Signal sources

Mặc định:

### Serper

Thu:

- People Also Ask;
- Related Searches;
- Autocomplete;
- organic titles/snippets/domains.

### Tavily / Exa

Không dùng để “tăng số keyword” bằng mọi giá.

Dùng để:

- phát hiện câu hỏi/chủ đề mà Google top results che khuất;
- tìm bài sâu;
- tìm expert/source concepts;
- phát hiện content gap.

### Internal signals

Khi có:

- existing Journal;
- customer questions;
- Search Console;
- website search;
- visitor/inquiry notes;
- approved Knowledge Cards.

Internal signal được ưu tiên vì gần khách thật của MOTGU hơn dữ liệu web chung.

## 5. Pipeline mini

```text
Seed
  ↓
Knowledge Recall
  ↓
Serper signals
  ↓
Normalize + Dedupe
  ↓
Question Expansion
  ↓
Classify
  ↓
Cluster
  ↓
Compare existing content
  ↓
Find MOTGU advantage
  ↓
Opportunity Map
  ↓
Pillar / Cluster suggestions
```

V1 chỉ cần một hoặc hai tầng mở rộng. Không tạo cây vô hạn.

## 6. Query/Question record

Mỗi signal chuẩn hóa nên có:

```yaml
query: "how do I know if a painting is original"
locale: en
source: people_also_ask
seed_query: "buy art in Hanoi"
question_type: trust
intent: evaluate
audience_stage: first_time_buyer
problem: authenticity_anxiety
topic: buying_original_art
entities:
  - artwork
signal_count: 2
query_quality: usable
```

Không cần mọi field có ngay từ provider. AI/rules có thể phân loại sau và giữ confidence.

`query_quality` gồm:

- `usable`: có ý nghĩa độc lập và đủ điều kiện lập Question/Cluster;
- `truncated`: query bị cắt hoặc kết thúc giữa ý;
- `malformed`: query hỏng, không có ý nghĩa tìm kiếm độc lập;
- `off_scope`: query hợp lệ nhưng thuộc art-making/artist-process, không thuộc buyer journey.

Signal gốc và provenance vẫn được giữ khi query là `truncated`, `malformed` hoặc
`off_scope`. Hai loại đầu không được tạo Question/Cluster/Opportunity. `off_scope`
có thể được giữ trong Question Map để truy nguyên nhưng không được làm support cho
NeedHypothesis buyer; nếu tạo opportunity theo dõi thì phải là `DO_NOT_WRITE` với
priority `NO`.

## 7. Taxonomy tối thiểu

### Question type

- `what`;
- `why`;
- `how`;
- `where`;
- `compare`;
- `trust`;
- `price`;
- `logistics`;
- `fit`;
- `visit`;
- `care`;
- `culture`;
- `other`.

### Intent

Dùng taxonomy chung của Settings:

- `learn`;
- `understand`;
- `compare`;
- `evaluate`;
- `trust`;
- `plan_visit`;
- `consider_purchase`;
- `post_purchase`.

### Audience stage

Tối thiểu:

- `curious`;
- `exploring`;
- `first_time_buyer`;
- `evaluating`;
- `ready_to_visit`;
- `ready_to_inquire`;
- `owner`.

Không coi taxonomy là chân lý cố định; có thể cập nhật sau pilot.

## 8. Clustering

Không gom chỉ vì keyword giống chữ nhau.

Hai query nên cùng cluster khi gần nhau ở nhiều chiều:

- cùng vấn đề;
- cùng intent;
- cùng câu trả lời cốt lõi;
- cùng audience stage;
- cùng topic/entity;
- nếu viết hai bài riêng sẽ dễ trùng intent.

Ví dụ:

```text
"how do I know a painting is original"
"how can I tell if art is authentic"
"how to verify an original painting"
```

→ một cluster `authenticity / trust`.

Nhưng:

```text
"original painting price"
```

có thể thuộc `price/value`, dù có chữ `original`.

## 9. Pillar / Cluster map

Keyword Plan không tự ép mọi topic phải có pillar.

Pillar candidate phù hợp khi:

- topic đủ rộng;
- có nhiều câu hỏi con thật;
- MOTGU có đủ knowledge/originality;
- có giá trị cập nhật lâu dài;
- có đường liên kết tự nhiên sang nhiều content/entity.

Khi dựng pillar, chỉ dùng các cluster buyer-relevant, cùng NeedHypothesis và có
`query_quality=usable`. Không cộng signal từ query truncated, malformed, off-scope,
artist-process hoặc cluster `DO_NOT_WRITE`. Nếu sau bộ lọc không còn đủ cluster thì
không ép tạo pillar.

Cluster candidate phù hợp khi:

- giải quyết một câu hỏi/hành vi hẹp;
- có intent rõ;
- không trùng bài hiện tại;
- có thể nối về pillar hoặc entity hữu ích.

Ví dụ:

```text
PILLAR
Buying Your First Original Painting
│
├── How do I know a painting is original?
├── Does art need to match my interior?
├── How much should I spend on my first painting?
├── How do I carry a painting home from Vietnam?
└── What if I know nothing about art?
```

### F1R2 — deterministic Content Architecture contract

Question cluster identity binds the canonical Need + locale + intent + audience stage +
answer job. Two questions sharing topic/intent but serving different journey stages are not
silently collapsed into one cluster.

`Content Architecture` is a derived, read-only projection over the exact Planner snapshot
and same-locale Content Coverage. It does not create another truth store.

Pillar candidate rules:

- only clusters already classified as usable and editorially ready contribute breadth;
- `DO_NOT_WRITE`, off-scope, malformed/truncated and unresolved clusters do not contribute;
- at least three distinct ready member clusters, distinct answer jobs and distinct primary
  questions are required by the current bounded policy;
- insufficient breadth returns no Pillar candidate rather than inventing one;
- an existing/selected same-Need same-locale Pillar blocks a new Pillar CREATE candidate;
- every Pillar freezes exact member cluster keys and the union of their SEARCH Signal refs;
- EN/VI architecture snapshots are independent; translated demand is not assumed equivalent.

Founder selection accepts either one exact Cluster candidate or one exact Pillar candidate.
The editorial role comes from the selected architecture snapshot, never from arbitrary client
input. A Pillar selection persists exactly one ContentOpportunity + one HumanSelection; it
does not create child ContentCases or invent parent/child relationships.

Durable architecture-selection lineage records the exact planner snapshot, architecture
snapshot/policy/candidate, editorial role, member cluster keys, selected Signal set and
selection payload. Exact replay uses this frozen receipt; stale/tampered lineage fails closed.

## 10. Content decision

Mỗi opportunity phải trả một trong:

- `CREATE` — nên tạo bài mới;
- `UPDATE` — bài hiện tại đã đúng intent nhưng cần bổ sung;
- `REFRESH` — bài tốt nhưng source/data đã cũ;
- `MERGE` — nhiều bài/ý đang cạnh tranh nhau;
- `LINK_ONLY` — không cần bài mới, chỉ cần nối nội dung/entity;
- `DO_NOT_WRITE` — không đủ giá trị hoặc quá xa MOTGU.

Đây là output quan trọng hơn một “keyword score”.

## 11. Opportunity dimensions

Không dùng một điểm tổng duy nhất làm quyết định.

Mỗi opportunity xem tối thiểu 7 chiều:

### Audience Fit

Có đúng nhóm người MOTGU muốn hiểu/phục vụ không?

### Problem Strength

Câu hỏi có gắn với pain/desire/objection thật không?

### Search Evidence

Có PAA/Related/Autocomplete/query/source signal đủ hợp lý không?

### Content Gap

Kết quả hiện tại có yếu, chung chung, bán hàng quá mức hoặc thiếu một góc quan trọng không?

### MOTGU Right-to-Win

MOTGU có dữ liệu/góc nhìn mà web chung khó có không?

Ví dụ:

- artist knowledge;
- real artwork;
- studio/process;
- visitor questions;
- Hanoi/local experience;
- real shipping/viewing practice.

### Business Connection

Có đường hữu ích sang Artist, Artwork, Visit, Workshop hoặc Inquiry không?

### Evidence Feasibility

Có khả năng tìm evidence đủ tốt không?

## 12. Priority

Thay vì score 0–100, V1 dùng mức dễ hiểu:

- `NOW` — rất phù hợp để thử sớm;
- `NEXT` — tốt nhưng chưa cần ngay;
- `LATER` — giữ lại quan sát;
- `NO` — không nên làm hiện tại.

Mỗi priority phải có reason ngắn.

Ví dụ:

```yaml
priority: NOW
reasons:
  - strong first-time buyer anxiety
  - many related questions
  - current results are mostly sales pages
  - MOTGU has real artwork and viewing experience
```

## 13. Niche Candidate — tìm ngách DNA MOTGU

Một ngách không được chọn chỉ vì ít cạnh tranh.

Niche Candidate phải trả lời:

1. nhóm người nào;
2. vấn đề gì;
3. họ dùng ngôn ngữ/câu hỏi gì;
4. web hiện trả lời thiếu gì;
5. MOTGU có tài sản riêng gì;
6. nội dung nào có thể chứng minh lợi thế đó;
7. có đường tự nhiên đến trải nghiệm/sản phẩm nào.

Công thức:

```text
Specific Audience
+ Specific Anxiety/Desire
+ Search Pattern
+ Weak Existing Answer
+ MOTGU-Owned Proof
= Niche Candidate
```

Ví dụ dạng giả thuyết:

```text
International first-time art buyers
+ fear of choosing wrong / authenticity / shipping
+ Hanoi/Vietnam travel context
+ generic sales-heavy SERP
+ real artist house + real artworks + practical local experience
```

Không coi ví dụ trên là kết luận cho tới khi research thật xác nhận.

## 14. Locale contract

Keyword Plan là locale-specific.

Không dịch keyword tiếng Việt sang tiếng Anh rồi coi là cùng search demand.

```text
Shared Topic / Problem
       │
       ├── EN Query Map
       └── VI Query Map
```

Có thể link hai map về cùng `ContentCase`/NeedHypothesis nhưng signals phải giữ locale riêng.

## 15. Existing content check

Trước khi đề xuất CREATE, kiểm tra Content Memory:

- có bài cùng primary intent không;
- có bài cùng question nhưng title khác không;
- có pillar/cluster liên quan không;
- có content cần refresh không;
- có internal link opportunity không.

Nếu chưa có Content Memory đầy đủ ở CE01, cho phép manual list/stub.

## 16. Output `KeywordPlan`

V1 output dạng JSON/Markdown đều được, nhưng schema logic gồm:

```yaml
keyword_plan:
  project: motgu
  locale: en
  seed_topic: "buy art in Hanoi"
  audiences: []
  problems: []
  topic_clusters: []
  questions: []
  pillar_candidates: []
  cluster_candidates: []
  niche_candidates: []
  content_decisions: []
  research_gaps: []
```

Mỗi candidate phải giữ source/signal refs để truy ra vì sao nó tồn tại.

## 17. Obsidian output

Không tạo một note cho từng keyword nhỏ.

Chỉ mirror các output có giá trị:

```text
20_Topics/
  buying-original-art.md

30_Research/
  keyword-plan-en-buying-art-hanoi.md
```

Topic hub nên tóm tắt:

- audience/problem;
- key question clusters;
- existing content;
- pillar/cluster map;
- niche candidates;
- open research gaps;
- linked Knowledge Cards.

## 18. Human review

Keyword Plan chỉ là đề xuất.

Human review nên trả lời ngắn:

- nhóm câu hỏi này có đúng MOTGU không?;
- có câu nào nghe như SEO nhưng khách thật ít quan tâm không?;
- MOTGU thực sự có gì riêng để nói?;
- ưu tiên NOW nào đáng đưa vào Golden Journal thử nghiệm?;
- có cluster nào nên bỏ/gộp?

## 19. Learning về sau

Khi có Search Console và hành vi thật:

```text
Keyword Plan hypothesis
    ↓
Published content
    ↓
Real queries / behaviour
    ↓
update signal strength
    ↓
LearningCandidate
```

Keyword Plan không tự đổi chỉ vì một bài có traffic tốt/xấu.

## 20. Scope V1

Làm:

- seed expansion;
- PAA/Related/Autocomplete ingest;
- normalize/dedupe;
- intent/problem classification;
- simple clustering;
- pillar/cluster suggestion;
- content decision;
- niche candidate;
- human review;
- Markdown/JSON output.

Chưa làm:

- keyword volume database lớn;
- paid keyword difficulty providers;
- backlink analysis;
- competitor crawling quy mô lớn;
- auto content calendar;
- auto publish;
- score 0–100 giả chính xác.

## 21. Definition of done V1

Mini module đạt khi từ một seed thật có thể:

1. thu PAA/Related/Autocomplete;
2. bỏ trùng;
3. phân nhóm theo problem/intent;
4. tạo một bản đồ topic dễ hiểu;
5. đề xuất pillar/cluster;
6. phát hiện ít nhất một Niche Candidate có lý do rõ;
7. phân biệt CREATE/UPDATE/MERGE/DO_NOT_WRITE;
8. giữ source refs;
9. cho human chọn một opportunity để đưa sang ContentCase/Golden Journal.
