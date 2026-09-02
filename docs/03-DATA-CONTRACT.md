# 03 — DATA CONTRACT

## 1. Nguyên tắc

Data model phải giúp trả lời được 5 câu hỏi cho mọi output quan trọng:

1. nó thuộc project nào;
2. nó được tạo trong run nào;
3. dựa trên source/evidence nào;
4. dùng settings/prompt/model version nào;
5. ai/điều gì đã duyệt nó.

## 2. Core entities

### Project

Tối thiểu:

- `id`
- `slug`
- `name`
- `status`
- `default_locale`
- `created_at`
- `updated_at`

V1 chỉ dùng `motgu`.

### Source

Đại diện nguồn dữ liệu gốc.

Fields tối thiểu:

- `id`
- `project_id`
- `source_type`
- `authority_level`
- `title`
- `external_id` nullable
- `canonical_url` nullable
- `locale` nullable
- `content_hash`
- `fetched_at` nullable
- `created_at`
- `updated_at`

`source_type` ví dụ:

- `wordpress`
- `woocommerce`
- `manual_document`
- `obsidian`
- `web`
- `research_api`

### SourceDocument

Canonical representation sau ingest.

- `id`
- `source_id`
- `document_version`
- `content_markdown`
- `metadata_json`
- `content_hash`
- `supersedes_id` nullable
- timestamps

Không overwrite lịch sử version quan trọng nếu source thay đổi.

### KnowledgeChunk

- `id` deterministic khi có thể
- `source_document_id`
- `ordinal`
- `text`
- `token_estimate`
- `fingerprint`
- `status`
- `metadata_json`

### Entity

Dùng để liên kết knowledge với thực thể MOTGU.

- `id`
- `project_id`
- `entity_type`
- `canonical_key`
- `display_name`
- `external_refs_json`
- timestamps

`entity_type` V1:

- `artist`
- `artwork`
- `workshop`
- `journal`
- `place`
- `material`
- `concept`

### Claim

Một phát biểu có thể kiểm chứng hoặc cần authority.

- `id`
- `project_id`
- `subject_entity_id` nullable
- `claim_text`
- `claim_type`
- `status`
- `confidence`
- timestamps

`claim_type`:

- `fact`
- `brand_statement`
- `interpretation`
- `opinion`

### Evidence

Nối claim với nguồn.

- `id`
- `claim_id`
- `source_document_id`
- `chunk_id` nullable
- `locator`
- `evidence_excerpt` bounded
- `support_type`
- `authority_level`
- `verified_at` nullable
- timestamps

`support_type`:

- `supports`
- `contradicts`
- `context_only`

Một claim factual quan trọng không được `publishable=true` nếu không có evidence hỗ trợ đủ authority theo rule.

### AudienceHypothesis

- `id`
- `project_id`
- `name`
- `description`
- `status`
- `evidence_summary`
- timestamps

### ProblemDesire

- `id`
- `project_id`
- `audience_hypothesis_id` nullable
- `type`: `pain | desire | question | curiosity | objection`
- `statement`
- `source`
- `status`

### ContentBrief

- `id`
- `project_id`
- `content_type`
- `content_role`
- `locale`
- `audience_hypothesis_id`
- `problem_desire_id`
- `primary_question`
- `intent`
- `desired_action`
- `content_hypothesis`
- `originality_statement`
- `must_include_json`
- `must_not_claim_json`
- `status`
- timestamps

### ContentRun

- `id`
- `project_id`
- `brief_id`
- `locale`
- `status`
- `current_step`
- `settings_snapshot_id`
- `started_at`
- `completed_at` nullable
- `failure_code` nullable
- `failure_message` nullable

### StepRun

- `id`
- `run_id`
- `step_key`
- `attempt`
- `status`
- `input_artifact_ids`
- `output_artifact_ids`
- `started_at`
- `completed_at`
- `error_json` nullable

Unique recommendation:

`(run_id, step_key, attempt)`

### Artifact

Mọi output trung gian/final có schema chung.

- `id`
- `run_id`
- `step_run_id` nullable
- `artifact_type`
- `locale`
- `version`
- `content_json` hoặc external object reference
- `content_hash`
- `created_at`

`artifact_type` ví dụ:

- `research_report`
- `evidence_ledger`
- `angle_set`
- `selected_angle`
- `outline`
- `draft`
- `review_report`
- `final_content`
- `publish_package`

### Approval

- `id`
- `run_id`
- `step_key`
- `artifact_id`
- `decision`: `approved | rejected | changes_requested`
- `actor_id`
- `comment`
- `created_at`

### ModelCall

- `id`
- `run_id`
- `step_run_id`
- `provider`
- `model`
- `purpose`
- `prompt_version`
- `input_tokens` nullable
- `output_tokens` nullable
- `cost` nullable
- `latency_ms`
- `status`
- `error_class` nullable
- timestamps

Không lưu secret hoặc full raw prompt nếu chứa dữ liệu cần che; prompt snapshot phải dùng cơ chế redaction phù hợp.

### QualityEvaluation

- `id`
- `run_id`
- `artifact_id`
- `evaluator_key`
- `evaluator_version`
- `result`: `pass | fail | warn`
- `score` nullable
- `findings_json`
- `created_at`

### PublishedContent

- `id`
- `project_id`
- `content_type`
- `locale`
- `final_artifact_id`
- `target`
- `external_id`
- `canonical_url`
- `published_at`
- `content_hash`

Unique/idempotency recommendation:

`(project_id, final_artifact_id, target)`

### PerformanceSnapshot

- `id`
- `published_content_id`
- `provider`
- `metric_date`
- `metrics_json`
- `imported_at`

### AudienceSignal

- `id`
- `project_id`
- `published_content_id` nullable
- `audience_hypothesis_id` nullable
- `signal_type`
- `signal_value`
- `strength`
- `source_provider`
- `observed_at`
- `evidence_json`

### LearningCandidate

- `id`
- `project_id`
- `learning_type`
- `statement`
- `evidence_json`
- `status`: `candidate | approved | rejected | superseded`
- `approved_by` nullable
- timestamps

### GoldenExample

- `id`
- `project_id`
- `published_content_id`
- `locale`
- `content_type`
- `golden_reason`
- `status`
- `approved_by`
- `approved_at`

## 3. Authority model

Khuyến nghị levels:

- `A1_CANONICAL_INTERNAL`: dữ liệu canonical do MOTGU sở hữu;
- `A2_PRIMARY_EXTERNAL`: nguồn chính thức/primary source;
- `A3_HIGH_TRUST`: museum, academic, institution, recognized expert publication;
- `A4_EDITORIAL`: báo chí/industry source đáng tin;
- `A5_GENERAL_WEB`: web thông thường;
- `A6_COMMUNITY`: forum/social/community.

Rule cụ thể phải cấu hình theo claim type, không mặc định “A1 luôn đúng cho mọi loại câu hỏi”.

## 4. Versioning

Không overwrite im lặng các object ảnh hưởng reproducibility:

- settings snapshot;
- prompt/recipe version;
- source document version;
- final content artifact;
- evaluator version;
- Golden Set membership.

## 5. Data retention

Giữ lâu dài:

- final artifacts;
- evidence ledger;
- approvals;
- published mapping;
- learning decisions;
- aggregate telemetry.

Có thể áp dụng retention ngắn hơn cho raw debug payload lớn nếu không cần audit, nhưng phải bảo đảm vẫn tái hiện được quyết định quan trọng.
