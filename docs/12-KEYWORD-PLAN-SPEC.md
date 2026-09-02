# 12 — KEYWORD PLAN SPEC

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
- optional ProblemDesire;
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
```

Không cần mọi field có ngay từ provider. AI/rules có thể phân loại sau và giữ confidence.

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

Có thể link hai map về cùng `ContentCase`/ProblemDesire nhưng signals phải giữ locale riêng.

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
