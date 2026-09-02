# 06 — MEMORY & LEARNING SPEC

## 1. Mục tiêu

Kho nội dung phải giúp ContentEngine tốt hơn theo thời gian nhưng không tự sao chép, tự củng cố lỗi hoặc biến output AI thành sự thật.

## 2. Memory layers

### Raw/Canonical Knowledge
Nguồn đã canonicalize, có provenance và fingerprint.

### Content Memory
Index các bài đã publish cùng topic, intent, audience, entities, claims, links và performance.

### Golden Memory
Tập nhỏ các bài/mẫu được human approve để làm baseline chất lượng và style.

### Learning Memory
Các learning candidate, decision và experiment result.

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

Nguyên tắc học từ OpenHuman:

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

Mỗi bài published nên index:

- topic;
- primary/secondary queries;
- intent;
- audience hypothesis;
- problem/desire;
- content role pillar/cluster;
- entities;
- claims;
- evidence set;
- internal links;
- angle;
- language/style tags;
- publish date;
- performance snapshots.

## 6. Pre-write memory check

Trước khi research sâu, workflow phải kiểm tra:

- đã có bài giải quyết câu hỏi này chưa;
- có bài cần update thay vì viết mới không;
- có nguy cơ trùng intent/cannibalization không;
- evidence nào có thể tái dùng;
- entity nào còn thiếu coverage;
- angle nào đã dùng quá nhiều.

Output: `memory_gap_report`.

## 7. Golden Set

Chỉ bài được human approve mới có thể vào Golden Set.

Tiêu chí nên gồm:

- factual/evidence pass;
- brand pass;
- useful/originality pass;
- human edit thấp hoặc edit cải thiện rõ;
- performance tốt hoặc được đánh giá editorial xuất sắc;
- đại diện cho locale/content type/intent cần regression.

Golden Set nhỏ, đa dạng, versioned.

## 8. Weak/Failure Set

Lưu các ví dụ lỗi có giá trị học:

- hallucination;
- generic AI tone;
- over-SEO;
- wrong audience;
- weak originality;
- misleading emotion;
- poor internal linking.

Dùng làm negative fixtures cho evaluator/regression.

## 9. Human Edit Delta

Sau final edit:

- diff draft/revised/final;
- phân loại edit: fact, tone, structure, wording, omission, CTA, source;
- tạo candidate patterns nếu lặp lại.

Không học trực tiếp từ một edit đơn lẻ thành global rule.

## 10. Learning Candidate lifecycle

```text
observed
→ candidate
→ gather evidence
→ human review
→ approved / rejected
→ experiment
→ promoted setting/rule OR archived
```

Mỗi candidate phải có:

- statement;
- scope;
- evidence refs;
- confidence;
- expected benefit;
- regression risk.

## 11. Learning loops

### Per-run
Human edits + evaluator findings + cost/latency.

### Batch 10–20 content
Tìm pattern về angle, problem, intent, model, recipe, edits.

### 1–3–6 tháng
Kết hợp Search + behaviour + conversion signals để cập nhật audience/problem hypotheses.

## 12. Anti-self-copy rules

- không dùng toàn bộ published corpus làm few-shot;
- giới hạn số Golden Examples;
- ưu tiên đa dạng examples;
- detect phrase/structure reuse;
- originality evaluator so với internal corpus;
- nếu similarity quá cao, yêu cầu rewrite hoặc đổi angle.

## 13. Summary tree — khi nào dùng

Không cần xây Memory Tree đầy đủ ngay V1.

Chỉ thêm hierarchical summaries khi corpus đủ lớn và retrieval latency/context bắt đầu xấu.

Thứ tự mở rộng:

1. raw sources + search;
2. entity/topic summaries;
3. content-cluster summaries;
4. global/project digest nếu có giá trị thật.

## 14. Definition of done

Memory/Learning V1 đạt khi:

- ingest chống trùng;
- provenance giữ xuyên suốt;
- pre-write duplicate/gap check hoạt động;
- Golden/Weak Set có lifecycle;
- learning candidate không tự promote;
- regression dùng được trước settings rollout.
