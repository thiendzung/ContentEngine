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
PHASE C — OPPORTUNITY MAP  CLOSED / PASS
PHASE D — CONTENT INPUT    CLOSED / PASS
PHASE E — WALKING SKELETON CLOSED / PASS
PHASE F — CE01 REVIEW      CLOSED / GO TO CE02
```

PR-A đã merge:

- PR: `#3 — CE01 PR-A — repository skeleton`;
- merge commit: `8e16c2817359191d0c4cd2e45a28f7eba8fa1a19`;
- toàn bộ baseline checks PASS trước merge.

PR-B đã merge và Gate B PASS. PR-C đã merge qua PR #6 với merge commit `cda4f738aff08abf827e2ce49418ea29f5af351f`. PR-D đã merge qua PR #7 với merge commit `fd86b67d587fdab663915fac106f751f34551c59`. PR-E ở PR #8 đã hoàn tất Walking Skeleton, Founder approved Journal V2, Assertion Audit V2 PASS và CE01 decision là `GO TO CE02`; PR #8 chờ final CI/review/merge.

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

Kết quả: **đủ 13/13**.

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
đánh giá bài → revision → Founder approval
        ↓
PHASE F — CE01 REVIEW
GO TO CE02
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

# PHASE C — OPPORTUNITY MAP MINI — CLOSED / PASS

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

PR-C merged through PR #6 at `cda4f738aff08abf827e2ce49418ea29f5af351f`.

---

# PHASE D — CONTENT INPUT — CLOSED / PASS

## D1. Editorial calibration

Task:

- T01.31 3–5 positive excerpts;
- T01.32 3–5 negative examples;
- T01.33 short human review form.

Không cần bài mẫu hoàn chỉnh. Đoạn ngắn đúng/sai giọng MOTGU là đủ.

CE01 approved pack:

- 4 positive English examples;
- 4 negative English examples;
- short human editorial review form;
- Founder approval: `APPROVE CALIBRATION + CONTENT DIRECTION` on `2026-09-06`.

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

Approved CE01 records:

- ContentCase: `cc_ce01_price_001`;
- LocaleVariant: `lv_ce01_price_en_001`;
- locale: `en`;
- content role: `cluster`;
- primary intent: `evaluate`;
- secondary intent: `trust`.

Primary question:

> What actually affects the price of an original painting, and what should a first-time buyer compare before deciding?

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

Locked CE01 EvidenceSet:

- ID: `es_ce01_price_v1`;
- status: `LOCKED_FOR_CE01`;
- locked by: `founder`;
- scope: narrow first-time-buyer price evaluation;
- sources: Smithsonian American Art Museum, Sotheby’s specialist estimate guidance, Getty provenance guidance, and canonical MOTGU Product & Data Contract;
- discovery sources from PR-B are not silently promoted into factual evidence.

Critical guard: this EvidenceSet does not support an exact MOTGU/artist base-pricing formula, investment claims, universal fair-price claims, or current product price/stock from memory.

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

Approved CE01 OriginalityPack:

- ID: `opack_ce01_price_v1`;
- status: `APPROVED_FOR_CE01`;
- live physical-work facts come from canonical MOTGU product data;
- current price/availability must not come from memory;
- artwork price can be separated from practical packaging/shipping/insurance costs;
- sale status and location are separate facts;
- editorial posture is calm, personal and low pressure.

Originality gap intentionally remains: there is no founder/artist explanation of the exact base-pricing method for a specific work. This is acceptable only while the content direction stays with understanding/evaluating a displayed price. Crossing into “how MOTGU prices its art” requires new evidence and human review.

### Gate D — PASS

- [x] ContentCase rõ;
- [x] locale rõ;
- [x] EvidenceSet đủ cho critical facts trong phạm vi đã khóa;
- [x] OriginalityPack có giá trị riêng MOTGU;
- [x] positive/negative voice examples đã được Founder approve.

Canonical content-input pack:

`docs/13-CE01-CONTENT-INPUT-PRICE.md`

Gate result:

`GATE D CLOSED / PASS`

PR-D merged through PR #7 at `fd86b67d587fdab663915fac106f751f34551c59`.

---

# PHASE E — WALKING SKELETON — CLOSED / PASS

Final checkpoint:

- Angle A: `PASS`;
- Outline V2: Founder approved — `APPROVE OUTLINE V2`;
- Artwork runtime fact lock: `PASS`;
- Draft EN V2: Founder approved — `APPROVE JOURNAL V2`;
- Assertion Audit V2: `PASS / ZERO CRITICAL UNSUPPORTED ASSERTIONS`;
- Human Gate 2: `PASS`.

## E1. Angle — T01.38

Sinh ít angle, mỗi angle phải trả lời:

- reader nhận được gì;
- khác web chung ở đâu;
- evidence có đủ không;
- MOTGU có quyền nói gì;
- risk nào còn thiếu.

Selected:

`ANGLE A — Read the price without treating it as a score`

## E2. Outline — T01.39

Mỗi section phải có purpose rõ.

Critical section map được tới evidence hoặc OriginalityPack.

Founder decision:

`APPROVE OUTLINE V2`

Canonical outline:

`docs/15-CE01-GOLDEN-JOURNAL-OUTLINE.md`

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

Draft V1 reached Founder review. Founder kept the concept/outline but required editorial revision because internal system language leaked into visible copy and English needed human polish.

Draft V2 applied the requested fixes and preserved the same factual scope.

Canonical candidate:

`docs/17-CE01-GOLDEN-JOURNAL-DRAFT-EN.md`

Founder decision:

`APPROVE JOURNAL V2`

## E4. Assertion Audit — T01.41

Sau Draft:

- bóc các factual assertions quan trọng;
- map lại EvidenceSet;
- unsupported critical assertion → BLOCK/REVIEW;
- interpretation phải được viết như interpretation.

Canonical audit:

`docs/18-CE01-GOLDEN-JOURNAL-ASSERTION-AUDIT.md`

Final result:

`PASS / ZERO CRITICAL UNSUPPORTED ASSERTIONS`

## HUMAN GATE 2 — T01.42 — PASS

Người duyệt trả lời:

1. bài có giúp đúng người đọc không?;
2. có gì mới/riêng của MOTGU không?;
3. có đoạn nào nghe chung chung/AI không?;
4. có fact nào đáng nghi không?;
5. có cảm xúc nhưng vẫn tự nhiên không?;
6. nếu là website thật, có muốn đăng không?

V1 review result:

`CONCEPT APPROVED / EDITORIAL REVISION REQUIRED`

Founder review identified editorial/process leakage rather than strategy failure. V2 removed that leakage, humanized English, reduced repetition, localized alt suggestions and improved reader-facing shipping/questions/CTA language.

Final Founder decision:

`APPROVE JOURNAL V2`

Không publish WordPress trong CE01.

---

# PHASE F — REVIEW & CLOSE — CLOSED / GO TO CE02

Task:

- T01.43 record failure notes;
- T01.44 CE01 gate decision.

Failure/improvement evidence:

- living loop: `docs/logs/2026-09-06-ce01-improvement-loop.md`;
- final closeout: `docs/logs/2026-09-06-ce01-closeout.md`.

T01.43 records research, opportunity-map, source/evidence, originality, voice/editorial, content-memory, dynamic-data and workflow failures/limitations without auto-changing global contracts.

Important retained lessons include:

- search signal != customer truth;
- provider count != research quality;
- IDs come from canonical artifacts;
- specific first-party Artwork anchors reduce generic content;
- runtime commerce facts stay dynamic;
- demo/seed content != production Content Memory;
- internal implementation language must never leak into visible copy;
- locale-facing alt/copy is separate from canonical media identity;
- Assertion Audit cannot replace human editorial review;
- SEO/AEO/AIO/GEO should share one human-first content system rather than four copy formulas.

## T01.44 — CE01 decision

Decision:

`GO TO CE02`

Reason:

- real signals and Opportunity Map are traceable;
- human selection works;
- Discovery and Evidence are separated;
- EvidenceSet and OriginalityPack support a bounded real case;
- a runtime-verified Artwork prevents generic synthesis;
- Angle/Outline/Human Review gates caught real problems before approval;
- one real Journal candidate reached human review and revision;
- final Assertion Audit has zero critical unsupported assertions;
- failure notes are preserved for later implementation.

GO does not mean production-ready. NeedHypothesis remains `PROPOSED`; CE02+ still need persistent models, approval state, durable execution, production research, Content Memory, publishing, measurement and learning.

## CE01 EXIT GATE

- [x] repo build/test sạch;
- [x] một founder-proposed NeedHypothesis + signals tạo Opportunity Map dễ hiểu;
- [x] human chọn được một opportunity có lý do rõ;
- [x] selected research/evidence sources tốt hơn việc lấy top Google mặc định;
- [x] có ContentCase + LocaleVariant thật;
- [x] có EvidenceSet + OriginalityPack;
- [x] một Journal thật tới human review;
- [x] zero critical unsupported assertion trong candidate được review;
- [x] failure notes rõ;
- [x] có quyết định GO / FIX BEFORE CE02 / STOP.

Final CE01 decision:

`PASS / GO TO CE02`

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
3. PR-C — Opportunity Map Mini — **MERGED / CLOSED / PASS**;
4. PR-D — editorial/content inputs — **MERGED / CLOSED / PASS**;
5. PR-E — walking skeleton + CE01 review — **PASS / READY FOR REVIEW**.

Mỗi PR phải có:

```text
GOAL
FILES CHANGED
EVIDENCE
RISKS / BLOCKERS
STATUS
NEXT
```

Không merge nếu task chưa có bằng chứng rõ. PR-E chỉ merge sau final CI xanh và Founder/reviewer review PR #8.