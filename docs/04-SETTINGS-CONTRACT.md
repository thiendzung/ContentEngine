# 04 — SETTINGS CONTRACT

## 1. Mục tiêu

Settings phải cho phép thay đổi hành vi ContentEngine mà không hardcode business rule vào code hoặc tạo một prompt khổng lồ khó kiểm soát.

Settings được tổ chức theo các khối nhỏ, có version, có scope và có override rõ ràng.

## 2. Nguồn sự thật duy nhất

V1 chốt như sau:

```text
Git
= schema + migration + seed mặc định

Database
= settings/prompt/recipe đang hoạt động + lịch sử version

SettingsSnapshot
= cấu hình hiệu lực bất biến của một run
```

Không duy trì cùng một setting/prompt ở nhiều nơi khác nhau.

Code không được chứa bản sao “ẩn” của prompt production.

## 3. Precedence

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

Mỗi ContentRun lưu `settings_snapshot_id` bất biến.

## 4. Project Settings

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

## 5. Brand DNA

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
    calm: high
    intimate: high
    poetic: medium
    commercial: low
    academic: low

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

Các mức `high/medium/low` chỉ là gợi ý. Ví dụ thật được ưu tiên hơn slider/số điểm.

## 6. Editorial Calibration Pack — nguồn chính cho giọng văn

Trước khi tự động hóa sâu, mỗi locale phải có một gói mẫu được người duyệt.

Tối thiểu khuyến nghị:

- 3–5 positive examples;
- 3–5 negative examples;
- có thể là đoạn ngắn, không cần bài hoàn chỉnh;
- tags theo `locale`, `content_type`, `intent`, `example_type`;
- ghi lý do tại sao tốt/xấu.

Ví dụ loại mẫu:

- opening;
- direct answer;
- artwork description;
- artist/context paragraph;
- CTA;
- full content khi có.

Không tự đưa mọi bài publish vào Calibration Pack.

## 7. Language DNA

Mỗi locale có Language DNA riêng.

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

## 8. Reader Transformation

Mỗi LocaleVariant nên có:

- `reader_before` từ ContentCase;
- `reader_after` từ ContentCase;
- `primary_emotion`;
- tối đa 2 `secondary_emotions`;
- `emotional_arc`.

Ví dụ:

```text
uncertainty → recognition → discovery → confidence
```

Không ép writer nhắc tên cảm xúc. Đây là hướng chuyển trạng thái của người đọc.

## 9. Audience Settings

Audience là giả thuyết, không phải chân lý.

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

## 10. Problem / Desire Library

Đây là taxonomy của NeedHypothesis, không phải bảng ProblemDesire riêng. Mỗi hypothesis
giữ source refs hoặc origin=founder_proposed, cùng support/contradiction/alternatives/gaps.
Observation nằm trong Signal; confidence không thay human review hoặc provenance.

Các nhóm:

- `pain`;
- `desire`;
- `question`;
- `curiosity`;
- `objection`.

Mỗi item có provenance nếu đến từ query, interview, behaviour hoặc customer interaction.

## 11. Content Type

V1:

### Journal

- answer/explain;
- build trust;
- create discovery;
- connect reader to MOTGU entities.

### Artwork

- explain the work;
- provide concrete facts;
- build trust;
- reduce buying/visiting uncertainty;
- connect to artist/story/context.

## 12. Content Role

- `pillar`: bài rộng, làm nền một chủ đề;
- `cluster`: giải quyết một câu hỏi/ngách cụ thể và nối về pillar/related entity.

Role không chọn chỉ theo keyword volume.

Topic/cluster relation phải map được về ContentItem sau khi bài tồn tại.

## 13. Intent

Taxonomy V1:

- `learn`;
- `understand`;
- `compare`;
- `evaluate`;
- `trust`;
- `plan_visit`;
- `consider_purchase`;
- `post_purchase`.

Một LocaleVariant có primary intent và optional secondary intent.

## 14. Writing Recipe

Recipe là cấu trúc chiến thuật, không phải template cứng.

Selector dùng:

```text
content_type
+ content_role
+ intent
+ audience stage
+ problem/desire type
+ locale
```

Ví dụ:

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

Writer được phép phá cấu trúc nhỏ nếu output tốt hơn và vẫn đúng intent/gates.

## 15. Originality Pack policy

Mỗi ContentCase phải có `OriginalityPack` trước Draft.

Pack ưu tiên:

- first-party MOTGU facts;
- artist quote có nguồn;
- artwork-specific observation;
- studio/process detail;
- visitor/customer question;
- practical MOTGU knowledge;
- synthesis mới có evidence.

Pack rỗng hoặc quá yếu → research thêm, đổi angle, update bài cũ hoặc không viết.

## 16. Language rules

Không dùng “NLP tricks” để giả giống người.

Dùng rules kiểm tra được:

- sentence rhythm variation;
- concrete nouns over vague claims;
- sensory details only when grounded;
- avoid generic transitions;
- avoid repeated AI phrases;
- avoid symmetrical list overuse;
- avoid unsupported superlatives;
- entity names clear and consistent;
- pronoun references unambiguous;
- concise direct answers khi query cần.

## 17. Prompt Registry

Prompt production được lưu/version trong Database qua registry rõ ràng.

Mỗi prompt có tối thiểu:

- `prompt_key`;
- `version`;
- `purpose`;
- `template/body`;
- `input contract`;
- `output schema`;
- `status`: draft/active/retired;
- change reason;
- approved_by/approved_at khi promote production.

Không hardcode prompt production trong workflow.

## 18. Model Routing

Settings map task → model policy.

```yaml
models:
  discovery_research:
    route: research
  evidence_research:
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

Router có fallback policy và budget.

## 19. Context Manifest

SettingsSnapshot không đủ để tái hiện output vì retrieval có thể thay đổi.

Mỗi model call quan trọng phải tham chiếu ContextManifest chứa:

- settings snapshot;
- prompt/recipe version;
- EvidenceSet;
- OriginalityPack;
- knowledge chunk IDs/hashes;
- Golden Example IDs;
- tool result refs/hashes.

## 20. Quality Thresholds

Hard gates không được biến thành một điểm trung bình duy nhất.

Ví dụ:

- unsupported critical factual assertion → FAIL;
- missing audience/problem → FAIL;
- originality absent → FAIL hoặc NEEDS_RESEARCH;
- source-copy risk cao → FAIL/REVIEW;
- minor style issue → WARN;
- Rank Math warning → WARN/FAIL theo loại lỗi, không theo overall score.

## 21. Change control

Mỗi thay đổi Settings production cần:

1. reason;
2. source/evidence;
3. version bump;
4. regression nếu ảnh hưởng output;
5. human approval;
6. rollout record.

Nếu thay đổi phá contract canonical, phải vào Contract Change Mode trước code.
