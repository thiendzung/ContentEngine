# 04 — SETTINGS CONTRACT

## 1. Mục tiêu

Settings phải cho phép thay đổi hành vi ContentEngine mà không hardcode business rule vào code hoặc tạo một prompt khổng lồ khó kiểm soát.

Settings được tổ chức theo các khối nhỏ, có version, có scope và có override rõ ràng.

## 2. Precedence

```text
SYSTEM DEFAULT
    ↓
PROJECT
    ↓
CONTENT TYPE
    ↓
LOCALE
    ↓
RUN OVERRIDE
```

Tầng dưới chỉ override key được cho phép.

Mỗi `ContentRun` phải lưu `settings_snapshot_id` bất biến để có thể tái hiện.

## 3. Project Settings

V1 project duy nhất: `motgu`.

Tối thiểu:

- project identity;
- canonical domain;
- default locale;
- supported locales;
- source authority rules;
- publishing target;
- measurement providers;
- feature flags.

## 4. Brand DNA

Brand DNA không phải một đoạn mô tả tự do duy nhất.

Schema đề xuất:

```yaml
brand:
  identity:
    category: "artist house"
    positioning: "..."
    promise: "..."

  worldview:
    principles:
      - "..."

  voice:
    calm: 0.9
    intimate: 0.8
    poetic: 0.5
    commercial: 0.2
    academic: 0.3

  emotional_signature:
    curiosity: 0.8
    discovery: 0.8
    intimacy: 0.8
    trust: 0.9
    urgency: 0.1

  boundaries:
    avoid:
      - fake scarcity
      - invented artist intention
      - inflated luxury language
      - generic AI cliches

  proof_preferences:
    prefer:
      - first-party facts
      - artist quotes with provenance
      - artwork-specific observation
      - studio/process evidence
```

Các giá trị số là preference, không phải công thức máy móc để tính câu chữ.

## 5. Language DNA

Mỗi locale có Language DNA riêng.

Mục tiêu: tạo văn phong tự nhiên trong chính ngôn ngữ đó, không dịch máy từ một bản gốc.

Schema đề xuất:

```yaml
language_dna:
  locale: en
  audience_context: "international traveller / art-curious reader"
  vocabulary:
    complexity: simple_to_moderate
    preferred_terms: []
    banned_phrases: []
  rhythm:
    sentence_length: varied
    paragraph_density: light
  sensory_language:
    enabled: true
    intensity: moderate
  rhetorical_questions:
    frequency: low
  metaphor:
    frequency: low_to_moderate
    must_be_grounded: true
  direct_answer:
    preferred: true
  CTA:
    tone: invitational
    pressure: low
```

`vi-VN` và `en` có config riêng.

## 6. Golden Style Examples

Brand/Language DNA phải hỗ trợ examples có kiểm soát:

- `positive_examples`;
- `negative_examples`;
- tags theo locale/content_type/intent;
- giới hạn số example đưa vào context;
- human approved only.

Không tự đưa mọi bài đã publish vào style examples.

## 7. Audience Settings

Audience được lưu như giả thuyết, không phải chân lý.

Mỗi audience profile có:

- name;
- context;
- motivations;
- anxieties;
- knowledge level;
- buying/visiting stage;
- evidence status;
- confidence;
- last reviewed date.

## 8. Problem / Desire Library

Các nhóm:

- `pain`;
- `desire`;
- `question`;
- `curiosity`;
- `objection`.

Mỗi item có provenance nếu đến từ query, interview, behaviour hoặc customer interaction.

## 9. Content Type

V1:

### Journal

Mục tiêu chính:

- answer/explain;
- build trust;
- create discovery;
- connect reader to MOTGU entities.

### Artwork

Mục tiêu chính:

- explain the work;
- provide concrete facts;
- build trust;
- reduce buying/visiting uncertainty;
- connect to artist/story/context.

## 10. Content Role

- `pillar`: trang/bài rộng, làm nền một chủ đề;
- `cluster`: giải quyết một câu hỏi/ngách cụ thể và nối về pillar/related entity.

Content role không được chọn chỉ theo keyword volume.

## 11. Intent

Taxonomy V1 đề xuất:

- `learn`;
- `understand`;
- `compare`;
- `evaluate`;
- `trust`;
- `plan_visit`;
- `consider_purchase`;
- `post_purchase`.

Một brief có primary intent và optional secondary intent.

## 12. Writing Recipe

Recipe là cấu trúc chiến thuật, không phải template cứng.

Recipe selector dùng:

```text
content_type
+ content_role
+ intent
+ audience stage
+ problem/desire type
```

Ví dụ recipe:

### `journal_direct_answer_story`

- answer first;
- context;
- concrete story/example;
- deeper insight;
- MOTGU-specific value;
- next useful step.

### `journal_beginner_guide`

- orientation;
- common uncertainty;
- simple framework;
- examples;
- mistakes to avoid;
- what to do next.

### `artwork_story_fact_trust`

- immediate artwork orientation;
- verified facts;
- visual/material observation;
- artist/context connection;
- ownership/visit practical information;
- related content.

Recipe phải cho phép writer phá cấu trúc nhỏ nếu evaluator xác nhận output tốt hơn và vẫn đúng intent.

## 13. Emotion Palette

Không “bơm cảm xúc” tùy ý.

Mỗi brief chọn tối đa 1 primary + 2 secondary emotions.

Ví dụ:

- curiosity;
- calm;
- intimacy;
- wonder;
- confidence;
- belonging;
- discovery.

Không dùng fear/urgency giả để tăng conversion.

## 14. NLP / Language Rules

Không dùng “NLP tricks” để giả giống người.

Thay bằng rules có thể kiểm tra:

- sentence rhythm variation;
- concrete nouns over vague claims;
- sensory details only when grounded;
- avoid generic transitions;
- avoid repeated AI phrases;
- avoid symmetrical list overuse;
- avoid unsupported superlatives;
- entity names clear and consistent;
- pronoun references unambiguous;
- concise direct answers where query demands.

## 15. Model Routing

Settings map task → provider/model policy.

Ví dụ:

```yaml
models:
  research:
    route: deep_research
  evidence_review:
    route: high_precision
  angle:
    route: creative_reasoning
  draft:
    route: longform_writer
  brand_review:
    route: style_reviewer
  factual_review:
    route: high_precision
```

Không hardcode tên model trong workflow business logic.

Router phải có fallback policy và cost/budget limits.

## 16. Quality Thresholds

Thresholds được versioned nhưng các hard gates quan trọng không được biến thành một điểm trung bình duy nhất.

Ví dụ:

- unsupported critical factual claim → FAIL;
- missing target audience/problem → FAIL;
- originality absent → FAIL hoặc NEEDS_RESEARCH;
- minor style issue → WARN;
- Rank Math technical warning → WARN/FAIL theo loại lỗi, không theo overall score.

## 17. Change control

Mỗi thay đổi Settings production cần:

1. reason;
2. source/evidence;
3. version bump;
4. regression run nếu ảnh hưởng output;
5. human approval;
6. rollout record.
