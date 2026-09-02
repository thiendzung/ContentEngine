# 07 — QUALITY EVAL SPEC

## 1. Mục tiêu

Quality system phải chặn nội dung sai, chung chung, lệch brand, sao chép nguồn hoặc vô ích trước publish; đồng thời tạo dữ liệu để cải thiện hệ thống.

Không dùng một điểm tổng duy nhất để quyết định publish.

Không dùng mô hình “AI viết → AI tự chấm → tự tin là tốt” làm cơ chế chính.

## 2. Ba lớp kiểm tra

### Lớp A — Deterministic checks

Ưu tiên dùng rule/code khi có thể kiểm tra rõ:

- required fields;
- canonical Artwork facts;
- evidence mapping tồn tại;
- critical unsupported assertion;
- broken/invalid internal link target;
- duplicate/content identity conflict;
- missing approval;
- source-copy/phrase-overlap threshold;
- publish package completeness.

### Lớp B — Model-based evaluators

Dùng model cho phần cần judgement:

- reader value;
- Brand/Language fit;
- originality;
- naturalness;
- structure;
- emotional arc;
- search/AI readability.

Kết quả model là signal, không phải truth tuyệt đối.

### Lớp C — Human review

Human quyết định cuối về:

- publishable;
- feels like MOTGU;
- useful;
- trustworthy;
- emotional effect;
- biggest issue.

V1 luôn cần final human approval.

## 3. Hard gates

### Evidence Gate
FAIL nếu factual assertion quan trọng không map được về evidence đủ authority hoặc evidence mâu thuẫn chưa xử lý.

### Audience/Problem Gate
FAIL nếu không xác định rõ người đọc và vấn đề/mong muốn chính.

### Originality Gate
FAIL/NEEDS_RESEARCH nếu `OriginalityPack` không đủ giá trị riêng hoặc bài chỉ là generic web summary.

### Brand Truth Gate
FAIL nếu bịa ý định nghệ sĩ, phóng đại thương hiệu, fake scarcity hoặc dùng thông tin MOTGU không được xác nhận.

### Source Integrity Gate
FAIL/REVIEW nếu copy/paraphrase quá sát nguồn hoặc corpus cũ vượt ngưỡng cho phép.

### Human Final Approval
Không publish tự động trong V1 nếu chưa có final approval.

## 4. Assertion Audit

Sau Draft/Revision và trước Final Approval:

```text
Draft/Final
→ extract factual/interpretive assertions
→ map về Claim/EvidenceSet
→ classify
→ hard fail nếu critical unsupported/contradicted
```

Assertion types tối thiểu:

- fact;
- brand statement;
- artist intent;
- interpretation;
- opinion;
- visual observation;
- practical/live information.

Live information như price/availability phải kiểm tra lại canonical source phù hợp, không lấy memory stale.

## 5. Evaluators

### `evidence_integrity`
Claim/assertion → evidence mapping, authority, contradiction, freshness.

### `reader_value`
Có trả lời primary question, có insight hữu ích, tránh filler.

### `brand_voice`
So output với Brand DNA, Language DNA và Calibration/Golden examples.

### `reader_transformation`
Kiểm tra bài có giúp người đọc đi từ `reader_before` tới `reader_after` một cách tự nhiên không.

Không chấm theo việc bài có dùng từ cảm xúc hay không.

### `originality`
So với:

- external research summary;
- internal corpus;
- OriginalityPack;
- generic AI patterns.

### `structure_readability`
Answer-first khi phù hợp, heading logic, đoạn dễ đọc, reference rõ.

### `search_ai_readability`
Kiểm tra:

- intent match;
- entity clarity;
- title/heading coherence;
- internal-link opportunities;
- concise answer passages;
- structured-data recommendation phù hợp content thật.

Không ép keyword density.

### `language_naturalness`
Theo locale:

- tự nhiên;
- không dịch máy;
- không sáo AI;
- nhịp câu hợp lý;
- từ ngữ đúng audience.

### `source_copy_risk`
Kiểm tra phrase overlap với:

- research/source excerpts;
- internal published corpus;
- Golden examples.

Mục tiêu: tránh copy nguồn và tránh tự sao chép chính mình.

### `conversion_integrity`
CTA là bước tiếp theo hữu ích, không ép bán.

## 6. Result contract

Mỗi evaluator trả:

```json
{
  "result": "pass|warn|fail",
  "findings": [],
  "evidence_refs": [],
  "repair_suggestions": [],
  "evaluator_version": "..."
}
```

Score số dùng để quan sát trend, không override hard gate.

## 7. Quality tối thiểu phải có trước Journal đầu tiên

Trước khi CE05 hoàn thiện, Walking Skeleton phải có:

- human editorial rubric;
- Calibration Pack `vi-VN` và `en` tối thiểu nếu cả hai được thử;
- evidence completeness check cơ bản;
- basic assertion audit;
- basic source-copy check;
- human review record.

Không đợi CE06 mới bắt đầu đánh giá chất lượng.

CE06 mở rộng thành hệ thống evaluator/regression đầy đủ.

## 8. Pairwise regression

Khi thử prompt/model/recipe mới, ưu tiên so:

```text
Baseline A vs Candidate B
```

Các câu hỏi:

- bản nào hữu ích hơn;
- bản nào giống MOTGU hơn;
- bản nào tự nhiên hơn;
- bản nào ít generic hơn;
- bản nào giữ evidence tốt hơn.

Pairwise result kết hợp hard gates, cost, latency và human preference.

Không promote chỉ vì candidate có average score cao hơn.

## 9. Rank Math role

Rank Math Pro là technical/content hygiene signal phụ.

Dùng để phát hiện:

- metadata thiếu;
- cấu trúc SEO cơ bản;
- indexability/config liên quan;
- các cảnh báo on-page hữu ích.

Không:

- tối ưu chỉ để đạt 100/100;
- ép writer nhồi keyword;
- coi Rank Math score là reader value hoặc business outcome.

## 10. Human evaluation

Form V1 ngắn:

- publishable? yes/no;
- factual issue? yes/no;
- feels like MOTGU? 1–5;
- useful to target reader? 1–5;
- changed reader state in a useful way? 1–5;
- generic/AI-like? 1–5;
- source-copy concern? yes/no;
- biggest issue;
- optional edit.

Human feedback đi vào learning pipeline.

## 11. Quality Gate output

Final gate trả:

- `PASS_FOR_HUMAN_APPROVAL`;
- `NEEDS_REVISION`;
- `NEEDS_RESEARCH`;
- `BLOCKED_FACTUAL`;
- `BLOCKED_SOURCE_INTEGRITY`.

Không evaluator nào tự publish.
