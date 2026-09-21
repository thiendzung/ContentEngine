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

## 22. Controlled Autopilot capability policy

AU-01 dùng `SettingsSnapshot` hiện có làm policy snapshot bất biến cho từng ContentRun. Không tạo permission store hoặc workflow engine thứ hai.

Schema V1:

```yaml
autopilot:
  capability_policy:
    schema_version: 1
    enabled: true
    workers:
      customer-map-worker:
        capabilities:
          - READ
          - WRITE_ARTIFACT
          - RUN_TOOL
          - WRITE_DATABASE
        allowed_actions:
          - read.customer
          - artifact.write.customer_map
          - database.write.customer_map
        forbidden_actions:
          - publish.execute
          - settings.change
          - workflow.change
        allowed_tools:
          - customer_store
          - dedupe
        budget_ceiling:
          max_tool_calls: 12
          max_model_calls: 2
          max_output_tokens: 8000
          max_estimated_cost: "1.50"
          max_wall_clock_seconds: 240
        max_timeout_seconds: 300
        max_attempts: 3
```

Capability policy phải đến từ ít nhất một `SettingsVersion` đang `active`, có `approved_by`, và ref đó phải nằm trong `SettingsSnapshot.source_version_refs_json`. Policy hiệu lực trong snapshot phải khớp chính xác policy đã duyệt; `run_override` hoặc snapshot tự tạo không được dùng để tự nâng quyền. V1 coi toàn bộ `capability_policy` là một khối policy nguyên tử, không ghép quyền từ nhiều nguồn mâu thuẫn.

Capability V1:
- `READ`;
- `WRITE_ARTIFACT`;
- `RUN_MODEL`;
- `RUN_TOOL`;
- `RESEARCH_EXTERNAL`;
- `WRITE_DATABASE`;
- `PUBLISH`;
- `CHANGE_SETTINGS`;
- `CHANGE_PROMPT`;
- `CHANGE_WORKFLOW`.

Action namespace V1 phải map được về đúng capability:
- `read.*` → `READ`;
- `artifact.write.*` → `WRITE_ARTIFACT`;
- `model.run.*` → `RUN_MODEL`;
- `tool.run.*` → `RUN_TOOL`;
- `research.external.*` → `RESEARCH_EXTERNAL`;
- `database.write.*` → `WRITE_DATABASE`;
- `publish.*` → `PUBLISH`;
- `settings.change.*` → `CHANGE_SETTINGS`;
- `prompt.change.*` → `CHANGE_PROMPT`;
- `workflow.change.*` → `CHANGE_WORKFLOW`.

ExecutionPlan phải bind exact:
- run + optional step;
- task + worker;
- SettingsSnapshot id + hash;
- input refs;
- expected output types;
- required capabilities;
- allowed/forbidden actions;
- allowed tools;
- budget;
- timeout;
- max attempts;
- stop conditions;
- required checks;
- reviewer;
- next-on-pass/fail;
- human-gate requirement.

Fail closed khi:
- worker/plan/policy không khớp;
- action/tool/capability vượt quyền;
- policy forbidden action bị plan bỏ quên;
- timeout/attempt/budget vượt ceiling;
- budget bắt buộc cho model/tool/research bị thiếu;
- SettingsSnapshot hoặc Artifact binding/hash không còn đúng;
- reviewer trùng với worker;
- timeout lớn hơn wall-clock budget của chính plan;
- authorize một plan khi run không còn `running`, hoặc step đã kết thúc/không còn là current step.

ExecutionPlan revision phải liên tục theo version trên cùng run/step/task; không được nhảy cóc version. Reviewer trong plan phải độc lập với worker.

`PUBLISH`, `CHANGE_SETTINGS`, `CHANGE_PROMPT`, `CHANGE_WORKFLOW` luôn yêu cầu `human_gate_required=true` ở contract. AU-01 chỉ xác nhận contract; AU-02 mới chịu trách nhiệm kiểm tra gate thực tế trước execution.

## LS-01 approved Lens guard sources

Lens candidates are derived from Customer Map + Coverage, but three high-risk Lens types need explicit approved authority before they may be SELECTed or MERGEd.

V1 stores these approved guard sources under the existing versioned Settings machinery:

```yaml
lens_selection:
  case_materials:
    - ref: case:authenticity-consultation
      need_hypothesis_id: null
      summary: Real customer consultation approved for this use
      provenance_ref: provenance:case-001
      rights_ref: rights:case-001
  pov_positions:
    - ref: pov:authenticity
      need_hypothesis_id: null
      statement: Authenticity claims should be grounded in traceable facts
      approval_ref: approval:pov:001
  causal_evidence:
    - ref: causal:example
      need_hypothesis_id: null
      statement: Approved causal statement
      source_ref: evidence:causal:001
      approval_ref: approval:causal:001
```

Rules:

- `need_hypothesis_id: null` means project/general applicability; otherwise the entry applies only to that exact Need.
- effective `lens_selection` settings must be reproducible from active, approved SettingsVersion refs carried by the exact run SettingsSnapshot;
- `run_override` or an arbitrary SettingsSnapshot cannot self-approve CASE, POV, or causal authority;
- conflicting settings layers fail closed; there is no implicit override policy;
- CASE requires all of: real-case ref, provenance ref, rights ref;
- POV requires an explicitly approved MOTGU position;
- CAUSES requires an explicitly approved causal evidence/source ref;
- settings prove permission/authority to consider a Lens; they do not replace downstream factual Evidence validation.
