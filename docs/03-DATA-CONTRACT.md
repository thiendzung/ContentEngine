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

### SettingsVersion

Một version cấu hình có thể được activate/retire.

- `id`
- `project_id` nullable cho system default
- `scope_type`: `system | project | content_type | locale`
- `scope_key`
- `version`
- `settings_json`
- `status`: `draft | active | retired`
- `change_reason`
- `approved_by` nullable
- timestamps

### SettingsSnapshot

Cấu hình hiệu lực bất biến của một run sau khi resolve precedence.

- `id`
- `project_id`
- `resolved_settings_json`
- `source_version_refs_json`
- `content_hash`
- `created_at`

### PromptDefinition

- `id`
- `prompt_key`
- `version`
- `purpose`
- `body`
- `input_contract_json`
- `output_schema_json`
- `status`: `draft | active | retired`
- `change_reason`
- `approved_by` nullable
- timestamps

### RecipeDefinition

- `id`
- `recipe_key`
- `version`
- `selector_json`
- `recipe_json`
- `status`: `draft | active | retired`
- `approved_by` nullable
- timestamps

### CalibrationExample

Ví dụ giọng văn/chất lượng được human approve, có thể tồn tại trước PublishedContent.

- `id`
- `project_id`
- `locale`
- `content_type` nullable
- `intent` nullable
- `example_type`
- `polarity`: `positive | negative`
- `content_text`
- `reason`
- `status`
- `approved_by`
- timestamps

### ContentCase

Đại diện bài toán nội dung chung, chưa gắn cứng vào một ngôn ngữ.

- `id`
- `project_id`
- `content_type`: `journal | artwork`
- `audience_hypothesis_id`
- `need_hypothesis_id`
- `content_opportunity_id`
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

Đại diện danh tính ổn định của nguồn dữ liệu gốc.

- `id`
- `project_id`
- `source_type`
- `title` nullable
- `publisher` nullable
- `author` nullable
- `canonical_url` nullable
- `locator` nullable
- `locale` nullable
- `commercial_bias` nullable
- `authority_hint` nullable
- `provenance_json`
- `captured_at`
- `fingerprint`
- timestamps

`source_type` ví dụ:

- `wordpress`
- `woocommerce`
- `manual_document`
- `obsidian`
- `web`
- `research_api`
- `media`

Source là danh tính ổn định của nguồn, không phải snapshot nội dung.

Trong một project:
`(project_id, fingerprint)` phải duy nhất.

Fingerprint được tạo từ locator ổn định:
`canonical_url`
hoặc `locator`
hoặc provenance `source_ref`.

Search rank không phải authority.
`authority_hint` chỉ là metadata hỗ trợ đánh giá.

Hash nội dung và thời điểm đọc thuộc `SourceDocument`, không thuộc `Source`.

### SourceDocument

Canonical representation sau ingest.

- `id`
- `source_id`
- `document_version`
- `canonical_url` nullable
- `fetched_at`
- `content_hash`
- `content_markdown`
- `metadata_json`
- `reader` nullable
- `provider` nullable
- `supersedes_id` nullable
- timestamps

Nội dung được canonicalize trước khi hash.

Cùng Source + cùng `content_hash`:
không tạo `SourceDocument` mới.

Nội dung thay đổi:
tạo `document_version` mới;
giữ version cũ;
`supersedes_id` trỏ về version trước khi có.

### KnowledgeChunk

- `id` deterministic khi có thể
- `source_document_id`
- `ordinal`
- `text`
- `token_estimate`
- `fingerprint`
- `status`
- `metadata_json`

ID deterministic từ:
`source_document_id + ordinal + text`.

Chunk phải có giới hạn rõ.

chunker version và giới hạn được lưu trong metadata.

Không âm thầm chia lại cùng SourceDocument bằng luật chunk khác.
Muốn thay đổi luật phải có quá trình version/rebuild rõ ràng sau này.

`metadata_json` có thể chứa derived entity-link metadata:

- `entity_linker_version`
- `entity_links`
- `entity_link_conflicts`

Entity-link metadata phải có version.

Retrieval không được tin `entity_links` từ linker version không tương thích.

Derived metadata không làm thay đổi SourceDocument truth/provenance.

### Entity

- `id`
- `project_id`
- `entity_type`
- `canonical_key`
- `canonical_name`
- `aliases_json`
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

Entity thuộc một project.

Baseline entity linking dùng `canonical_name` + `aliases_json` đã normalize.

Alias chỉ map đến đúng một Entity trong project mới được tự link.

Alias mơ hồ:
không tự chọn;
ghi conflict;
chờ bước xử lý rõ ràng hơn sau này.

Entity link chỉ là metadata hỗ trợ retrieval.
Nó không tự trở thành Claim, Evidence hay factual truth.

### Knowledge Retrieval

Retrieval V1:

- luôn scope theo project;
- có thể scope theo locale;
- chỉ trả active KnowledgeChunk;
- chỉ lấy SourceDocument version mới nhất của mỗi Source;
- relevance được xét trước authority/bias;
- exact phrase, matched terms và entity overlap là relevance signals;
- source_type preference chỉ dùng khi caller yêu cầu rõ;
- authority_hint là một dimension riêng;
- commercial_bias là một dimension riêng;
- search rank/position không phải authority;
- không gộp mọi dimension thành một “authority score” tuyệt đối;
- ranking policy phải explicit/versioned;
- cùng input + cùng persisted state + cùng policy phải cho thứ tự ổn định.

PR-B không thêm vector infrastructure.

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
- `approved_by` nullable until approval
- `approval_reason` nullable until approval
- `snapshot_hash` nullable until approval; exact hash of the approved pack snapshot

An `approved` OriginalityPack must retain non-empty approval metadata and its exact
snapshot hash. Approved snapshot content is immutable; a stale or mutated snapshot must
fail closed. A `draft` or `retired` pack cannot cross a Journal handoff gate.

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

### Signal

Quan sát gốc, không chứa diễn giải như fact. `SearchSignal` của provider là payload thấp
tầng; PR-C normalize vào Signal với nguồn, scope và provenance, không thành customer truth.

- `id`, `project_id`
- `source_kind`: `MARKET | SEARCH | MOTGU`
- `scope`: `market_web | motgu_site | motgu_direct`
- `observed_text` (trích dẫn/quan sát có giới hạn)
- `source_url` / `external_id` (ít nhất một locator truy được về nguồn)
- `locale`, `context`, `captured_at`, `observed_at` nullable
- `fingerprint`, `duplicate_of` nullable, `independence_group` nullable
- `provenance`: provider/method, source/document/artifact ref, locator, hash/version
- `published_content_id` / `content_version_id` nullable cho hành vi tại MOTGU
- `metric_refs` nullable

Source kind không phải cấp độ tin cậy. Search Console = SEARCH/motgu_site;
PAA = SEARCH/market_web; review bên ngoài = MARKET/market_web;
inquiry = MOTGU/motgu_direct. Giữ dữ liệu trực tiếp riêng tư bằng locator nội bộ,
ẩn thông tin nhận dạng không cần thiết, không đưa nguyên tin nhắn/email vào public content.
Fingerprint hỗ trợ dedupe; cùng review được repost không tăng số nguồn độc lập.
Không tự khẳng định independence chỉ vì URL khác nhau.

### NeedHypothesis

- `id`
- `project_id`
- `audience_hypothesis_id` nullable
- `type`: `pain | desire | question | curiosity | objection`
- `statement`
- `audience_scope`, `situation`
- `origin`: `founder_proposed | signal_derived`
- `status`: `PROPOSED | TESTING | SUPPORTED | REJECTED | INSUFFICIENT_EVIDENCE`
- `support_signal_refs`, `contradict_signal_refs`
- `alternative_explanations`, `missing_evidence`
- `version`, `reviewed_by`, `reviewed_at`, `review_reason`

Founder hypothesis được phép chưa có signal; phải ghi thiếu evidence.
SUPPORTED cần review có phạm vi, tín hiệu độc lập lặp lại và tín hiệu khách MOTGU phù hợp.
Không có ngưỡng số review tự động; thiếu/ít hành vi không tự chứng minh REJECTED.
Mọi thay đổi trạng thái giữ lịch sử và source refs, không overwrite observation.

### ContentOpportunity

- `id`, `project_id`, `need_hypothesis_id`, `locale`
- `reader`, `situation`, `need`, `question`, `intent`, `promise`
- `motgu_material_refs`, `material_gaps`, `existing_content_refs`
- `what_is_actually_new`, `next_discovery_step`
- `decision`: `CREATE | UPDATE | REFRESH | MERGE | LINK_ONLY | DO_NOT_WRITE`
- `priority`: `NOW | NEXT | LATER | NO`, `reasons`
- `signal_refs`, `suggested_content_type`, `suggested_role` nullable
- `version`, `selected_by`, `selected_at`, `selection_reason`

UPDATE/REFRESH/MERGE/LINK_ONLY yêu cầu existing target refs. Human selection là quyết
định thử nội dung, không phải xác nhận hypothesis. Không tạo bài chỉ vì còn keyword.

### ContentExperiment

- `id`, `project_id`, `content_opportunity_id`, `need_hypothesis_id`, `hypothesis_version`
- `content_item_id`, `content_version_id`, `published_content_id` nullable trước publish
- `expected_behaviour`, `measurement_plan`, `metric_definitions`, `minimum_evidence`
- `review_window_start`, `review_window_end`
- `status`: `PLANNED | RUNNING | REVIEWED`
- `result`: `PENDING | SUPPORTS | CONTRADICTS | INCONCLUSIVE`
- `observation_refs`, `alternative_explanations`, `reviewed_by`, `reviewed_at`

Định nghĩa expected behaviour/cách đo trước publish; review gắn đúng version và cửa sổ.
Result bổ sung evidence qua Signal/ContentPerformanceObservation; không tự đổi hypothesis
hoặc settings. Dwell time không tự chứng minh interest; shipping inquiry không tự chứng
minh fear of fraud. Không có conversion khi traffic ít là INCONCLUSIVE.

### Thay thế model cũ trước CE02

`ProblemDesire` được thay bằng NeedHypothesis (giữ `type` pain/desire/question/... như
taxonomy). `AudienceSignal` được thay bằng Signal có source_kind/scope rõ. Không tạo
hai bảng song song. `AudienceHypothesis` vẫn mô tả nhóm người; `LearningCandidate` vẫn
là đề xuất thay đổi quy tắc. `ContentCase.content_hypothesis` là giả thuyết hiệu quả
biên tập, không thay NeedHypothesis. CE01 chưa có các bảng cũ nên không cần migration
runtime trong PR-B; CE02 tạo schema mới và cập nhật mọi foreign key theo contract này.

### ContentRun

- `id`
- `project_id`
- `content_case_id`
- `locale_variant_id`
- `content_item_id` nullable
- `run_mode`: `create | update | refresh | localize | eval`

Replay creates an `eval` ContentRun from frozen baseline inputs/context.

An `eval` run is comparison-only:

- it must not publish;
- it must not create durable external side effects;
- it must not automatically promote settings, prompts, recipes, or models.

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
- `memory_overlap`
- `journal_context`

### ContextManifest

Snapshot model đã nhìn thấy gì cho một call/step quan trọng.

- `id`
- `run_id`
- `step_run_id`
- `settings_snapshot_id`
- `prompt_version`
- `recipe_version`
- `evidence_set_id`
- `originality_pack_id` nullable
- `context_artifact_id` nullable
- `approved_knowledge_refs_json`
- `knowledge_chunk_refs_json`
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

### Job

Operational record cho durable job queue.

- `id`
- `run_id`
- `step_run_id`
- `status`: `queued | leased | completed | failed | cancelled`
- `available_at`
- `attempt`
- `dedupe_key`
- `lease_owner` nullable
- `lease_expires_at` nullable
- timestamps

### OutboxIntent

Durable intent cho side effect quan trọng như publish.

- `id`
- `run_id`
- `intent_type`
- `idempotency_key`
- `payload_ref`
- `status`: `pending | processing | completed | failed | needs_reconciliation`
- `external_ref` nullable
- `attempt`
- `error_json` nullable
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

### ContentPerformanceObservation

Một nhận xét có cấu trúc từ metrics, chưa phải learning rule.

- `id`
- `published_content_id`
- `content_version_id` nullable
- `observation_type`
- `statement`
- `metric_refs_json`
- `data_status`: `insufficient | early_signal | repeated_pattern`
- `observed_at`

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
