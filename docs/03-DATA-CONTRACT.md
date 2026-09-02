# 03 — DATA CONTRACT

## 1. Nguyên tắc

Data model phải giúp trả lời được 7 câu hỏi cho mọi output quan trọng:

1. nó thuộc project nào;
2. nó thuộc content case/content item nào;
3. nó được tạo trong run nào;
4. dựa trên source/evidence nào;
5. model đã nhìn thấy context nào;
6. dùng settings/prompt/model version nào;
7. ai/điều gì đã duyệt nó.

## 2. Core entities

### Project

Tối thiểu:

- `id`
- `slug`
- `name`
- `status`
- `default_locale`
- timestamps

V1 chỉ dùng `motgu`.

### ContentCase

Đại diện bài toán nội dung chung, chưa gắn cứng vào một ngôn ngữ.

- `id`
- `project_id`
- `content_type`: `journal | artwork`
- `audience_hypothesis_id`
- `problem_desire_id`
- `desired_action`
- `content_hypothesis`
- `originality_statement`
- `reader_before`
- `reader_after`
- `status`
- timestamps

Một ContentCase có thể có nhiều LocaleVariant.

### LocaleVariant

Chiến lược riêng cho từng ngôn ngữ/thị trường.

- `id`
- `content_case_id`
- `locale`
- `content_role`
- `primary_question`
- `primary_intent`
- `secondary_intent` nullable
- `primary_query` nullable
- `keyword_notes_json`
- `emotion_arc_json`
- `must_include_json`
- `must_not_claim_json`
- `status`
- timestamps

Unique recommendation: `(content_case_id, locale)`.

### ContentItem

Danh tính ổn định của một bài/trang trong một locale.

- `id`
- `project_id`
- `content_case_id`
- `locale_variant_id`
- `content_type`
- `status`
- `canonical_key`
- timestamps

Không tạo ContentItem mới chỉ vì bài được sửa hoặc refresh.

### ContentVersion

Một phiên bản cụ thể của ContentItem.

- `id`
- `content_item_id`
- `version_no`
- `final_artifact_id`
- `change_reason`
- `status`: `draft | approved | published | superseded`
- `created_by_run_id`
- timestamps

Unique recommendation: `(content_item_id, version_no)`.

### Source

Đại diện nguồn dữ liệu gốc.

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
- timestamps

`source_type` ví dụ:

- `wordpress`
- `woocommerce`
- `manual_document`
- `obsidian`
- `web`
- `research_api`
- `media`

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
- `visual_observation`

### Evidence

Nối claim với nguồn.

- `id`
- `claim_id`
- `source_document_id` nullable
- `chunk_id` nullable
- `media_observation_id` nullable
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

### EvidenceSet

Snapshot bất biến của các evidence được phép dùng trong một run/version.

- `id`
- `project_id`
- `content_case_id`
- `version`
- `evidence_ids_json`
- `content_hash`
- `locked_at`
- `locked_by`

Không sửa EvidenceSet đã dùng để tạo output; tạo version mới nếu research thay đổi.

### OriginalityPack

Nguyên liệu riêng của MOTGU được writer phép dùng.

- `id`
- `content_case_id`
- `item_refs_json`
- `summary`
- `status`
- `approved_at` nullable

Item có thể là first-party fact, artist quote, artwork observation, studio/process detail, visitor question hoặc practical MOTGU knowledge.

### MediaAsset

Đại diện ảnh/media thật.

- `id`
- `project_id`
- `entity_id` nullable
- `source_id`
- `external_id` nullable
- `content_hash`
- `rights_status`
- `metadata_json`
- timestamps

### MediaObservation

Một quan sát cụ thể từ MediaAsset.

- `id`
- `media_asset_id`
- `observation_text`
- `method`: `human | model | metadata`
- `confidence`
- `status`: `candidate | approved | rejected`
- `approved_by` nullable
- timestamps

Artwork writer không được biến model observation chưa được chấp nhận thành canonical fact.

### AudienceHypothesis

- `id`
- `project_id`
- `name`
- `description`
- `status`
- `evidence_summary`
- `confidence`
- timestamps

### ProblemDesire

- `id`
- `project_id`
- `audience_hypothesis_id` nullable
- `type`: `pain | desire | question | curiosity | objection`
- `statement`
- `source`
- `status`

### ContentRun

- `id`
- `project_id`
- `content_case_id`
- `locale_variant_id`
- `content_item_id` nullable
- `run_mode`: `create | update | refresh | localize`
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

Unique recommendation: `(run_id, step_key, attempt)`.

### Artifact

- `id`
- `run_id`
- `step_run_id` nullable
- `artifact_type`
- `locale` nullable
- `version`
- `content_json` hoặc external object reference
- `content_hash`
- `created_at`

`artifact_type` ví dụ:

- `discovery_research_report`
- `evidence_research_report`
- `evidence_ledger`
- `evidence_set`
- `originality_pack`
- `memory_gap_report`
- `angle_set`
- `selected_angle`
- `outline`
- `draft`
- `review_report`
- `assertion_audit`
- `final_content`
- `publish_package`

### ContextManifest

Snapshot model đã nhìn thấy gì cho một call/step quan trọng.

- `id`
- `run_id`
- `step_run_id`
- `settings_snapshot_id`
- `prompt_version`
- `recipe_version`
- `evidence_set_id`
- `knowledge_chunk_ids_json`
- `golden_example_ids_json`
- `tool_result_refs_json`
- `content_hash`
- `created_at`

### ContentAssertion

Factual/interpretive assertion được trích từ draft/final để audit.

- `id`
- `artifact_id`
- `assertion_text`
- `assertion_type`
- `claim_id` nullable
- `evidence_id` nullable
- `support_status`: `supported | unsupported | contradicted | interpretation | opinion`
- `severity`
- timestamps

Critical unsupported assertion → hard fail.

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
- `context_manifest_id` nullable
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

### ToolCall

- `id`
- `run_id`
- `step_run_id`
- `tool_key`
- `request_fingerprint`
- `result_ref` nullable
- `latency_ms`
- `status`
- `error_class` nullable
- timestamps

### QualityEvaluation

- `id`
- `run_id`
- `artifact_id`
- `evaluator_key`
- `evaluator_version`
- `evaluator_type`: `deterministic | model | human`
- `result`: `pass | fail | warn`
- `score` nullable
- `findings_json`
- `created_at`

### PublishedContent

Mapping ContentItem với WordPress/external target.

- `id`
- `project_id`
- `content_item_id`
- `target`
- `external_id`
- `canonical_url`
- `current_content_version_id`
- `published_at`
- timestamps

Unique recommendation: `(project_id, content_item_id, target)`.

### PublishEvent

Lịch sử publish/update.

- `id`
- `published_content_id`
- `content_version_id`
- `idempotency_key`
- `status`
- `external_revision_id` nullable
- `published_at` nullable
- `error_json` nullable

### PerformanceSnapshot

Giữ raw/aggregate payload của provider để audit.

- `id`
- `published_content_id`
- `provider`
- `window_start`
- `window_end`
- `raw_metrics_json`
- `imported_at`

### PerformanceMetric

Các chỉ số lõi được chuẩn hóa để so giữa bài.

- `id`
- `published_content_id`
- `provider`
- `metric_date`
- `metric_name`
- `metric_value`
- `dimensions_json`

Metric V1 ưu tiên: `impressions`, `clicks`, `sessions`, `engaged_sessions`, `artwork_transition`, `visit_transition`, `workshop_transition`, `inquiry`.

### AudienceSignal

- `id`
- `project_id`
- `published_content_id` nullable
- `audience_hypothesis_id` nullable
- `signal_type`
- `signal_value`
- `strength`
- `sample_size` nullable
- `source_provider`
- `observed_at`
- `evidence_json`

### LearningCandidate

- `id`
- `project_id`
- `learning_type`
- `statement`
- `scope_json`
- `evidence_json`
- `sample_size` nullable
- `observation_window` nullable
- `confidence`
- `status`: `candidate | approved | rejected | superseded`
- `approved_by` nullable
- timestamps

### GoldenExample

- `id`
- `project_id`
- `content_item_id` nullable
- `content_version_id` nullable
- `locale`
- `content_type`
- `example_type`: `full_content | excerpt | opening | artwork_description | cta | other`
- `golden_reason`
- `status`
- `approved_by`
- `approved_at`

Golden seed examples có thể tồn tại trước khi có PublishedContent.

### TopicNode / ContentRelation

Mô hình tối thiểu cho pillar/cluster và internal linking.

`TopicNode`:

- `id`
- `project_id`
- `name`
- `canonical_key`
- `status`

`ContentRelation`:

- `from_content_item_id`
- `to_content_item_id` nullable
- `topic_node_id` nullable
- `relation_type`: `pillar_of | cluster_of | supports | related_entity`

## 3. Authority model

- `A1_CANONICAL_INTERNAL`: dữ liệu canonical do MOTGU sở hữu;
- `A2_PRIMARY_EXTERNAL`: nguồn chính thức/primary source;
- `A3_HIGH_TRUST`: museum, academic, institution, recognized expert publication;
- `A4_EDITORIAL`: báo chí/industry source đáng tin;
- `A5_GENERAL_WEB`: web thông thường;
- `A6_COMMUNITY`: forum/social/community.

Rule cụ thể cấu hình theo claim type, không mặc định “A1 luôn đúng cho mọi loại câu hỏi”.

## 4. Versioning

Không overwrite im lặng các object ảnh hưởng reproducibility:

- settings snapshot;
- prompt/recipe version;
- source document version;
- evidence set;
- context manifest;
- final content version;
- evaluator version;
- Golden Set membership.

## 5. Data retention

Giữ lâu dài:

- final artifacts/content versions;
- evidence ledger/evidence set;
- assertion audit;
- approvals;
- published mapping/events;
- learning decisions;
- aggregate telemetry.

Có thể áp dụng retention ngắn hơn cho raw debug payload lớn nếu không cần audit, nhưng vẫn phải tái hiện được quyết định quan trọng.
