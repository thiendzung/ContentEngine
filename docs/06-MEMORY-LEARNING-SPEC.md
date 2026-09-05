# 06 — MEMORY & LEARNING SPEC

## 1. Mục tiêu

Kho nội dung phải giúp ContentEngine tốt hơn theo thời gian nhưng không tự sao chép, tự củng cố lỗi hoặc biến output AI thành sự thật.

## 2. Memory layers

### Raw/Canonical Knowledge
Nguồn đã canonicalize, có provenance và fingerprint.

### Content Memory
Index `ContentItem` + `ContentVersion` đã publish cùng topic, intent, audience, entities, claims, links và performance.

### Golden Memory
Tập nhỏ ví dụ được human approve để làm baseline chất lượng/style.

### Learning Memory
Learning candidate, decision và experiment result.

## 3. Ingest pipeline

```text
Source
→ canonicalize
→ fingerprint/dedupe
→ chunk
→ metadata/entity extraction
→ quality/admission rule
→ persist
→ retrieval index
→ optional summaries
```

Nguyên tắc:

- deterministic IDs khi có thể;
- raw source vẫn giữ để truy nguyên;
- dropped item không bị xóa nếu cần audit;
- summary không thay thế source;
- retrieval phải đưa provenance refs.

## 4. Retrieval

Mỗi task truy xuất theo scope:

- project;
- locale;
- content type;
- entity;
- topic;
- audience/problem;
- freshness;
- authority.

Ranking kết hợp:

- lexical relevance;
- semantic relevance;
- source authority;
- freshness;
- entity match;
- approved/golden status.

Không để similarity score một mình quyết định truth.

## 5. Content Memory fields

Mỗi ContentItem/Version nên index:

- ContentCase;
- LocaleVariant;
- topic;
- primary/secondary queries;
- intent;
- audience hypothesis;
- problem/desire;
- pillar/cluster relation;
- entities;
- claims/evidence set;
- internal links;
- angle;
- language/style tags;
- publish/update date;
- performance metrics.

Không coi version mới là một bài mới nếu vẫn cùng ContentItem.

## 6. Pre-write memory check

Trước research sâu, workflow kiểm tra:

- đã có ContentItem giải quyết câu hỏi này chưa;
- nên update/refresh thay vì tạo mới không;
- có nguy cơ trùng intent/cannibalization không;
- evidence nào có thể tái dùng;
- entity/topic nào còn thiếu coverage;
- angle/cấu trúc nào đã dùng quá nhiều.

Output: `memory_gap_report` + recommendation:

- `create_new`;
- `update_existing`;
- `refresh_existing`;
- `merge`;
- `do_not_write`.

## 7. Editorial Calibration Pack và Golden Set

### Seed Calibration Pack

Có ngay trước bài AI đầu tiên:

- positive excerpts;
- negative excerpts;
- human approved;
- theo locale/content type.

Mục tiêu: cho writer/evaluator một chuẩn giọng thật của MOTGU từ đầu.

### Golden Set

Sau khi có bài thật, chỉ item/version được human approve mới có thể vào Golden Set.

Tiêu chí:

- factual/evidence pass;
- brand pass;
- useful/originality pass;
- human edit hợp lý;
- performance tốt hoặc editorial quality xuất sắc;
- đại diện cho locale/content type/intent cần regression.

Golden Set nhỏ, đa dạng, versioned.

## 8. Weak/Failure Set

Lưu ví dụ lỗi có giá trị học:

- hallucination;
- unsupported assertion;
- generic AI tone;
- over-SEO;
- wrong audience;
- weak originality;
- source-copy/phrase-copy;
- misleading emotion;
- poor internal linking.

Dùng làm negative fixtures.

## 9. Human Edit Delta

Sau final edit:

- diff draft/revised/final;
- phân loại edit: fact, tone, structure, wording, omission, CTA, source;
- tạo candidate patterns nếu lặp lại.

Không học một edit đơn lẻ thành global rule.

## 10. Learning Candidate lifecycle

```text
observed
→ candidate
→ gather evidence
→ human review
→ approved / rejected
→ experiment
→ regression
→ promoted setting/rule OR archived
```

Mỗi candidate có:

- statement;
- scope;
- evidence refs;
- sample size khi có;
- observation window;
- confidence;
- expected benefit;
- regression risk.

## 11. Minimum-evidence rule

ContentExperiment phải khóa hypothesis version, expected behaviour, metric definitions,
minimum evidence và review window trước publish. Kết quả SUPPORTS/CONTRADICTS/INCONCLUSIVE
bổ sung observation refs, không tự promote hypothesis/settings. Giữ alternative explanations
và negative evidence. SUPPORTED chỉ dùng sau human review với phạm vi rõ và tín hiệu MOTGU
phù hợp; thiếu traffic không đồng nghĩa bác bỏ nhu cầu. Signal luôn giữ nguồn ban đầu.

Hệ thống phải phân biệt:

- signal thú vị;
- pattern lặp lại;
- learning đủ mạnh để đổi strategy.

Một learning candidate không được promote chỉ vì một bài tốt/xấu.

Tùy loại learning, settings có thể định nghĩa:

- minimum sample;
- minimum time window;
- minimum repeated observations;
- required human review;
- required regression.

Nếu chưa đủ, output phải nói rõ: `INSUFFICIENT_EVIDENCE`.

## 12. Learning loops

### Per-run
Human edits + evaluator findings + cost/latency.

### Batch 10–20 content
Tìm pattern về angle, problem, intent, model, recipe, edits.

### 1–3–6 tháng
Kết hợp Search + behaviour + conversion signals để cập nhật audience/problem hypotheses.

## 13. Anti-self-copy và anti-source-copy

- không dùng toàn bộ published corpus làm few-shot;
- giới hạn Golden Examples;
- ưu tiên đa dạng examples;
- detect phrase/structure reuse với corpus nội bộ;
- detect phrase overlap với research/source excerpts;
- không paraphrase sát nguồn chỉ để “trông khác”;
- originality evaluator so với internal corpus + external source set;
- similarity cao → review/rewrite/đổi angle.

## 14. Context Memory

Mỗi model call quan trọng phải có `ContextManifest`.

Learning không chỉ hỏi “model nào tốt”, mà còn phải hỏi:

- model thấy evidence nào;
- Golden Examples nào được đưa vào;
- knowledge chunks nào được dùng;
- context quá nhiều/thiếu ở đâu.

Không kết luận model/prompt từ output nếu không biết context đã dùng.

## 15. Summary tree — khi nào dùng

Không xây Memory Tree đầy đủ ngay V1.

Chỉ thêm hierarchical summaries khi corpus đủ lớn và retrieval latency/context bắt đầu xấu.

Thứ tự:

1. raw sources + search;
2. entity/topic summaries;
3. content-cluster summaries;
4. global/project digest nếu có giá trị thật.

## 16. Definition of done

Memory/Learning V1 đạt khi:

- ingest chống trùng;
- provenance giữ xuyên suốt;
- ContentItem/version không bị nhầm thành bài mới;
- pre-write duplicate/gap check hoạt động;
- Calibration/Golden/Weak Set có lifecycle;
- learning candidate không tự promote;
- candidate biết khi nào chưa đủ evidence;
- regression dùng được trước settings rollout.
