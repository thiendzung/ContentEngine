# 07 — QUALITY EVAL SPEC

## 1. Mục tiêu

Quality system phải chặn nội dung sai, chung chung, lệch brand hoặc vô ích trước publish; đồng thời tạo dữ liệu để cải thiện hệ thống.

Không dùng một điểm tổng duy nhất để quyết định publish.

## 2. Hard gates

### Evidence Gate
FAIL nếu claim factual quan trọng không có evidence đủ authority hoặc evidence mâu thuẫn chưa xử lý.

### Audience/Problem Gate
FAIL nếu không xác định rõ người đọc và vấn đề/mong muốn chính.

### Originality Gate
FAIL/NEEDS_RESEARCH nếu bài không có giá trị riêng, dữ liệu riêng, quan sát riêng hoặc synthesis mới đủ rõ.

### Brand Truth Gate
FAIL nếu bịa ý định nghệ sĩ, phóng đại thương hiệu, fake scarcity hoặc dùng thông tin MOTGU không được xác nhận.

### Human Final Approval
Không publish tự động trong V1 nếu chưa có final approval.

## 3. Evaluators

### `evidence_integrity`
Kiểm tra claim → evidence mapping, authority, contradiction, unsupported statements.

### `reader_value`
Kiểm tra bài có trả lời đúng primary question, có actionable/useful insight, tránh filler.

### `brand_voice`
So output với Brand DNA, Language DNA, positive/negative Golden examples.

### `originality`
So với:

- general web research summary;
- internal published corpus;
- generic AI phrasing patterns.

Tìm phần thực sự chỉ MOTGU có thể nói tốt.

### `structure_readability`
Kiểm tra answer-first khi phù hợp, heading logic, đoạn dễ đọc, reference rõ.

### `search_ai_readability`
Kiểm tra:

- intent match;
- entity clarity;
- title/heading coherence;
- internal link opportunities;
- concise answer passages;
- structured data recommendations phù hợp content thật.

Không ép keyword density.

### `language_naturalness`
Theo locale:

- tự nhiên;
- không dịch máy;
- không câu sáo AI;
- nhịp câu đa dạng vừa phải;
- từ ngữ đúng audience.

### `conversion_integrity`
CTA phải là bước tiếp theo hữu ích, không ép bán.

## 4. Result contract

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

Score số có thể dùng để quan sát trend, không override hard gate.

## 5. Rank Math role

Rank Math Pro là technical/content hygiene signal phụ.

Dùng để phát hiện các vấn đề như:

- metadata thiếu;
- cấu trúc SEO cơ bản;
- indexability/config liên quan;
- các cảnh báo on-page hữu ích.

Không:

- tối ưu chỉ để đạt 100/100;
- ép writer nhồi keyword;
- coi Rank Math score là reader value hoặc business outcome.

## 6. Regression eval

Mỗi candidate change về model/prompt/recipe/retrieval/settings chạy trên Golden Set và Weak Set.

Report phải so:

- hard-gate pass/fail;
- evaluator deltas;
- hallucination/evidence errors;
- brand/style regressions;
- originality;
- cost;
- latency;
- human preference nếu có.

Không promote nếu có regression nghiêm trọng dù average score tăng.

## 7. Human evaluation

V1 cần form ngắn, không gây mệt:

- publishable? yes/no;
- factual issue? yes/no;
- feels like MOTGU? 1–5;
- useful to target reader? 1–5;
- generic/AI-like? 1–5;
- biggest issue;
- optional edit.

Human feedback lưu vào learning pipeline.

## 8. Quality Gate output

Final gate trả một trong:

- `PASS_FOR_HUMAN_APPROVAL`;
- `NEEDS_REVISION`;
- `NEEDS_RESEARCH`;
- `BLOCKED_FACTUAL`.

Không tự publish từ evaluator.
