# CE01 — WALKING SKELETON RUNBOOK

## 1. Mục tiêu duy nhất

CE01 chỉ có một mục tiêu:

> Từ một NeedHypothesis do founder đề xuất và các MARKET/SEARCH/MOTGU Signal truy nguyên
> được, hệ thống tạo Opportunity Map dễ hiểu, chọn được một cơ hội nội dung tốt, research
> được nguồn tốt và tạo một Journal thật để người duyệt đánh giá.

Seed đầu tiên chưa được gọi là nhu cầu khách MOTGU đã xác nhận. CE01 phải giữ ranh giới:

```text
Signal = điều quan sát được
NeedHypothesis = điều có thể đúng
ContentOpportunity = điều đáng thử
ContentExperiment = cách học sau publish
```

Không coi “backend chạy được” hay “API gọi được” là hoàn thành CE01.

## 2. Trạng thái hiện tại

```text
PHASE A — FOUNDATION       CLOSED
PHASE B — RESEARCH SPIKE   CLOSED / PASS
PHASE C — OPPORTUNITY MAP  PASS / READY FOR REVIEW
PHASE D — CONTENT INPUT    NEXT
PHASE E — GOLDEN JOURNAL   PENDING
PHASE F — CE01 REVIEW      PENDING
```

PR-A đã merge:

- PR: `#3 — CE01 PR-A — repository skeleton`;
- merge commit: `8e16c2817359191d0c4cd2e45a28f7eba8fa1a19`;
- toàn bộ baseline checks PASS trước merge.

PR-B đã merge và Gate B PASS. PR-C hiện ở PR #6, đã hoàn thành Gate C và chờ review/merge trước khi mở PR-D.

## 3. Kết quả cuối CE01

Phải có đủ:

1. repo chạy sạch;
2. một founder-proposed NeedHypothesis và Signal thật;
3. một Opportunity Map mini gồm Keyword/Question Map;
4. một opportunity được người duyệt chọn;
5. một ContentCase + LocaleVariant;
6. một EvidenceSet thủ công/chọn lọc;
7. một OriginalityPack MOTGU;
8. Angle;
9. Outline;
10. Draft;
11. basic assertion audit;
12. human review;
13. danh sách lỗi/học được để quyết định CE02.

## 4. Luồng thực thi

```text
PHASE A — FOUNDATION
repo chạy được
        ↓
PHASE B — RESEARCH SPIKE
1 founder-proposed hypothesis → search → traceable signals/sources
        ↓
PHASE C — KEYWORD PLAN MINI
questions → clusters → opportunities
        ↓
HUMAN GATE 1
chọn 1 opportunity
        ↓
PHASE D — CONTENT INPUT
ContentCase + LocaleVariant + EvidenceSet + OriginalityPack
        ↓
PHASE E — WALKING SKELETON
Angle → Outline → Draft → Assertion Audit
        ↓
HUMAN GATE 2
đánh giá bài
        ↓
PHASE F — CE01 REVIEW
GO / FIX / STOP
```

---

# PHASE A — FOUNDATION — CLOSED

## A1. Repository skeleton

Task:

- T01.1 xác nhận branch `ce01-walking-skeleton` từ `main` sạch;
- T01.2 FastAPI backend tối thiểu;
- T01.3 Next.js frontend shell tối thiểu;
- T01.4 root scripts;
- T01.5 `.env.example`;
- T01.6 PostgreSQL + migration framework;
- T01.7 module directories;
- T01.8 health/version endpoint.

### Checklist A1

- [x] backend start được;
- [x] frontend start được;
- [x] database connect được;
- [x] `/health` trả OK;
- [x] không có API key trong Git;
- [x] module `research` tồn tại;
- [x] chưa thêm logic ngoài CE01.

## A2. Quality baseline

Task:

- T01.9 backend lint/type/test;
- T01.10 frontend lint/type/build;
- T01.11 OpenAPI + frontend generated types;
- T01.12 CI;
- T01.13 clean install test.

### Gate A — PASS

- [x] install từ đầu được;
- [x] build sạch;
- [x] tests nền pass;
- [x] CI pass;
- [x] repo không có file tạm/debug theo verification của PR-A.

Evidence chính: PR #3 merge thành công sau khi backend install/lint/typecheck/migration/tests/OpenAPI và frontend install/type generation/lint/typecheck/build đều PASS.

---

# PHASE B — RESEARCH SPIKE — CLOSED / PASS

## B1. Provider seam

Task:

- T01.14 config keys: Serper, Tavily, Exa, Jina; Brave optional;
- T01.15 SearchProvider + Serper adapter;
- T01.16 Tavily/Exa source-discovery seam;
- T01.17 Jina selected URL reader;
- T01.18 bounded raw research artifact;
- T01.21 budget + stop-when-sufficient.

Default rule:

```text
MOTGU knowledge trước
→ Serper
→ đủ thì dừng
→ Tavily nếu Google nhiều sales/SEO noise
→ Exa nếu cần nguồn sâu/second-hop
→ Jina chỉ đọc URL đã chọn
```

### Checklist B1

- [x] không gọi mọi provider cho mọi query;
- [x] mỗi call giữ provider/query/result refs;
- [x] timeout/error không làm mất run;
- [x] search position không dùng làm authority score;
- [x] raw SERP không ghi vào Obsidian;
- [x] có giới hạn số query/pages/calls.

## B2. One founder-proposed hypothesis + real signals

Chỉ chọn **một** NeedHypothesis do founder đề xuất cho CE01.

Hypothesis phải bắt đầu từ pain/desire/question, không bắt đầu từ search volume.

Seed mặc định cho PR-B:

> First-time art buyer worries about choosing the wrong painting.

Đây là **founder-proposed hypothesis để test Research**, giữ status `PROPOSED`;
MARKET/SEARCH signals tìm thấy chưa biến nó thành MOTGU customer truth.

Output tối thiểu:

- PAA;
- Related Searches;
- Autocomplete;
- organic titles/snippets/domains;
- vài source candidates ngoài top sales pages.

## B3. Source quality spike

Task:

- T01.19 one-step second-hop;
- T01.20 manual Deep Research import shape.

Phải chứng minh ít nhất một ví dụ:

```text
Google sales/SEO page
→ citation / expert / report
→ source gốc tốt hơn
```

Mỗi selected source tối thiểu phải giữ:

- URL;
- source type;
- commercial bias: low / medium / high / unknown;
- why selected;
- found via provider/method;
- original / second-hop / intermediate;
- intended use: discovery / evidence candidate / context only.

Không cần tạo điểm authority giả chính xác kiểu 83/100.

Manual ChatGPT/Gemini Deep Research được phép nhập dưới dạng:

```text
Research Report
+ Original Source URLs
```

Report AI không tự trở thành factual authority. Muốn dùng fact phải lần về source gốc.

### Gate B — PASS

- [x] một founder-proposed hypothesis chạy được;
- [x] Serper trả discovery signals;
- [x] có Artsy editorial candidate tốt hơn nhóm sales-heavy để discovery/context;
- [x] 3 selected URLs đọc được qua Jina;
- [x] biết provider nào được gọi và vì sao;
- [x] source đã chọn giữ provenance và lý do chọn;
- [x] second-hop candidates được trích xuất, giữ parent URL và lọc social/share/CDN noise.

Evidence run: 6 provider calls, 27 signals, 17 source candidates, 3 documents,
8 second-hop candidates; CI `33999734730` PASS. Artsy chưa được dùng như factual
authority; authority verification thuộc Evidence Research sau PR-B.

Fresh canonical run sau khi Founder cấu hình API keys:

- Research artifact: `ce01-research-spike-20260906T013152Z.json`;
- SHA-256: `7d8b1b59f735a69b7b4f84b08ad5d2af33246a9545f20e8fad15df61c09b682a`;
- Serper, Tavily, Exa, Jina chạy qua live HTTP path;
- Brave không được gọi vì fallback không cần;
- 34 signals;
- NeedHypothesis vẫn `PROPOSED`.

---

# PHASE C — OPPORTUNITY MAP MINI — PASS / READY FOR REVIEW

Task:

- T01.22 collect signals;
- T01.23 normalize/dedupe;
- T01.24 classify problem/intent/audience stage;
- T01.25 simple clustering;
- T01.26 pillar/cluster candidates;
- T01.27 Niche Candidates;
- T01.28 content decision;
- T01.29 priority.

Keyword/Question Map là công cụ con. Output chính phải dễ đọc và truy nguyên:

Không trả bảng hàng nghìn keyword.

Một plan tốt phải cho người duyệt thấy:

```text
Signal refs
→ NeedHypothesis + support/contradiction/alternatives/gaps
→ Question Cluster
→ Search Signals
→ MOTGU Right-to-Win
→ Suggested Content Role
→ Decision
→ Priority
```

Mỗi opportunity phải có:

- audience;
- problem/desire;
- primary question;
- intent;
- pillar / cluster / artwork / other suggestion;
- MOTGU advantage;
- evidence feasibility;
- CREATE / UPDATE / REFRESH / MERGE / LINK_ONLY / DO_NOT_WRITE;
- NOW / NEXT / LATER / NO;
- source/signal refs.

### Gate C evidence

Canonical cleaned Opportunity Map:

`artifacts/research/ce01-opportunity-map-20260906T014147Z.json`

Kết quả:

- 34 Signals;
- 9 Questions;
- 4 Clusters;
- 4 Opportunities;
- broad Pillar không được tạo vì không có core `choosing` cluster;
- `artist_process` → `DO_NOT_WRITE / NO`;
- `painting_technique` → `DO_NOT_WRITE / NO`;
- `negotiation` → `CREATE / LATER`;
- `price` → `CREATE / LATER`.

Không có NicheCandidate ở real-seed vì chưa có MOTGU Right-to-Win material. Đây là kết quả đúng: hệ thống không được tự bịa lợi thế MOTGU để tạo niche candidate.

## HUMAN GATE 1 — T01.30 — PASS

Founder chọn **một** opportunity:

- topic: `price`;
- opportunity ID: `opp_ea484183ba36c6b2`;
- selected by: `founder`;
- selected at: `2026-09-06T02:06:02.678002+00:00`.

Selection reason:

> Price is the strongest buyer-relevant cluster in the verified real-seed run, with repeated search signals and clear purchase-evaluation intent. It is selected for the first Golden Journal experiment, subject to MOTGU-owned material, stronger evidence and editorial review before drafting.

Selected artifact:

`artifacts/research/ce01-opportunity-map-20260906T020602Z.json`

SHA-256:

`55c5657ce6a2fb54f2b8328405bddea727dd634a23fdf33b1ba841845a5c4a2e`

ContentExperiment draft:

- ID: `exp_cdc69b59a413393c`;
- status: `PLANNED`;
- result: `PENDING`;
- NeedHypothesis remains `PROPOSED`.

Selection cho phép thử content; không tự đổi NeedHypothesis sang SUPPORTED.

Gate C PASS không có nghĩa `price` đã được chứng minh là nhu cầu thật, cũng không có nghĩa MOTGU đã có lợi thế riêng. Hai việc đó phải được kiểm tra ở Phase D bằng EvidenceSet + OriginalityPack.

---

# PHASE D — CONTENT INPUT — NEXT

## D1. Editorial calibration

Task:

- T01.31 3–5 positive excerpts;
- T01.32 3–5 negative examples;
- T01.33 short human review form.

Không cần bài mẫu hoàn chỉnh. Đoạn ngắn đúng/sai giọng MOTGU là đủ.

## D2. ContentCase

Task:

- T01.34 one real ContentCase;
- T01.35 one LocaleVariant.

ContentCase tối thiểu phải rõ:

- audience;
- pain/desire;
- primary question;
- reader before;
- reader after;
- desired action;
- content hypothesis.

LocaleVariant tối thiểu:

- locale;
- query language;
- title direction;
- language/voice notes.

## D3. EvidenceSet

Task T01.36.

Không cần tự động hóa full Evidence Research ở CE01.

Chọn thủ công nguồn đủ tốt rồi khóa một EvidenceSet nhỏ.

Mỗi critical fact phải biết:

```text
claim
→ source
→ locator
```

## D4. OriginalityPack

Task T01.37.

Phải có ít nhất một nguyên liệu MOTGU riêng:

- artist knowledge;
- Artwork thật;
- studio/process;
- visitor question;
- local Hanoi experience;
- practical viewing/shipping knowledge;
- first-party observation.

Nếu OriginalityPack rỗng, không viết chỉ để hoàn thành task.

### Gate D

- [ ] ContentCase rõ;
- [ ] locale rõ;
- [ ] EvidenceSet đủ cho critical facts;
- [ ] OriginalityPack có ít nhất một giá trị riêng;
- [ ] positive/negative voice examples đã có.

---

# PHASE E — WALKING SKELETON

## E1. Angle — T01.38

Sinh ít angle, mỗi angle phải trả lời:

- reader nhận được gì;
- khác web chung ở đâu;
- evidence có đủ không;
- MOTGU có quyền nói gì;
- risk nào còn thiếu.

Human chọn một angle.

## E2. Outline — T01.39

Mỗi section phải có purpose rõ.

Critical section map được tới evidence hoặc OriginalityPack.

Human duyệt outline trước Draft.

## E3. Draft — T01.40

V1 cho phép một model adapter tạm thời.

Không xây model router phức tạp nếu chưa cần.

Writer chỉ nhận:

- ContentCase;
- LocaleVariant;
- approved Angle;
- approved Outline;
- EvidenceSet;
- OriginalityPack;
- editorial calibration excerpts.

## E4. Assertion Audit — T01.41

Sau Draft:

- bóc các factual assertions quan trọng;
- map lại EvidenceSet;
- unsupported critical assertion → BLOCK/REVIEW;
- interpretation phải được viết như interpretation.

## HUMAN GATE 2 — T01.42

Người duyệt trả lời:

1. bài có giúp đúng người đọc không?;
2. có gì mới/riêng của MOTGU không?;
3. có đoạn nào nghe chung chung/AI không?;
4. có fact nào đáng nghi không?;
5. có cảm xúc nhưng vẫn tự nhiên không?;
6. nếu là website thật, có muốn đăng không?

Kết quả:

- `PUBLISHABLE_DIRECTION`;
- `NEEDS_CHANGES`;
- `REJECT_DIRECTION`.

Không publish WordPress trong CE01.

---

# PHASE F — REVIEW & CLOSE

Task:

- T01.43 record failure notes;
- T01.44 CE01 gate decision.

Phải ghi riêng:

- research failure;
- keyword-plan failure;
- source-quality failure;
- evidence gap;
- voice failure;
- originality failure;
- content workflow failure;
- technical failure.

Không tự sửa global settings từ một bài thử.

## CE01 EXIT GATE

Chỉ đóng CE01 khi tất cả điều sau đúng:

- [x] repo build/test sạch;
- [x] một founder-proposed NeedHypothesis + signals tạo Opportunity Map dễ hiểu;
- [x] human chọn được một opportunity có lý do rõ;
- [ ] selected research sources tốt hơn việc lấy top Google mặc định;
- [ ] có ContentCase + LocaleVariant thật;
- [ ] có EvidenceSet + OriginalityPack;
- [ ] một Journal thật tới human review;
- [ ] zero critical unsupported assertion trong candidate được review;
- [ ] failure notes rõ;
- [ ] có quyết định GO / FIX BEFORE CE02 / STOP.

## CE01 NON-GOALS

Không làm trong phase này:

- production Content Memory;
- WordPress publish;
- Artwork engine;
- full worker/queue durability;
- full automatic Obsidian knowledge ingest;
- multi-project;
- full bilingual production;
- keyword volume database;
- backlinks/difficulty suite;
- autonomous approval;
- tự học và tự sửa prompt/settings.

## Quy tắc chia PR

Không gom CE01 thành một PR khổng lồ.

1. PR-A — repository skeleton — **MERGED / CLOSED**;
2. PR-B — research spike — **MERGED / CLOSED / PASS**;
3. PR-C — Opportunity Map Mini — **PASS / READY FOR REVIEW**;
4. PR-D — editorial/content inputs — **NEXT**;
5. PR-E — walking skeleton + CE01 review — **PENDING**.

Mỗi PR phải có:

```text
GOAL
FILES CHANGED
EVIDENCE
RISKS / BLOCKERS
STATUS
NEXT
```

Không merge nếu task chưa có bằng chứng rõ.