# 05 — HARNESS SPEC

## 1. Mục tiêu

Harness là lớp đảm bảo mỗi lần tạo nội dung diễn ra có cấu trúc, có checkpoint, có thể resume, đo được và tái hiện được.

Harness không quyết định nội dung viết gì; nó điều phối cách workflow chạy.

## 2. Run Graph V1

```text
CREATE_RUN
  ↓
BRIEF
  ↓
KNOWLEDGE_RECALL
  ↓
RESEARCH
  ↓
EVIDENCE_LOCK
  ↓
ANGLE
  ↓
WAIT_ANGLE_APPROVAL
  ↓
OUTLINE
  ↓
WAIT_OUTLINE_APPROVAL (configurable)
  ↓
DRAFT
  ↓
REVIEW
  ↓
REVISE
  ↓
QUALITY_GATE
  ↓
WAIT_FINAL_APPROVAL
  ↓
PACKAGE
  ↓
PUBLISH (explicit action)
  ↓
COMPLETE
```

## 3. Bounded loops

Không có loop vô hạn.

Ví dụ:

- research expansion: tối đa N vòng theo budget;
- draft revise: mặc định tối đa 2 vòng;
- provider retry: theo error class và retry policy;
- evaluator repair: bounded.

Khi hết budget/iteration:

- dừng;
- lưu root cause;
- trả trạng thái có thể hiểu;
- cho phép người dùng quyết định retry/modify/cancel.

## 4. Checkpoint contract

Checkpoint được tạo sau mỗi step hoàn thành và trước mỗi human approval gate.

Checkpoint tối thiểu giữ:

- run state;
- step outputs/artifact IDs;
- settings snapshot ID;
- evidence set ID/version;
- model call ledger refs;
- pending approval;
- retry counters.

Không cần lưu lại secret/provider session token.

## 5. Resume semantics

Khi service restart:

1. load latest durable checkpoint;
2. kiểm tra step nào đã complete;
3. không chạy lại side-effect đã xác nhận;
4. tiếp tục từ step pending/running theo recovery policy;
5. nếu step running không biết kết quả external call, reconciliation trước retry.

## 6. Approval gate

Approval là state chính thức, không phải comment phụ.

Actions:

- approve;
- reject;
- request_changes.

Mỗi decision lưu actor/time/artifact version/comment.

Nếu artifact thay đổi sau approval, approval cũ không tự áp dụng cho version mới.

## 7. Budget contract

Budget có thể cấu hình theo run và step:

- max model calls;
- max tool calls;
- max input tokens/context estimate;
- max output tokens;
- max estimated cost;
- max wall-clock duration;
- max research sources;
- max revise loops.

Stop budget phải tạo explicit failure/paused reason.

## 8. Model call adapter

Workflow gọi model qua interface chung:

```text
ModelRouter.resolve(task, project, locale, settings)
    ↓
ModelClient.generate(request)
```

Request chứa:

- task key;
- prompt version;
- structured context refs;
- output schema;
- budgets.

Response chuẩn hóa:

- text/structured output;
- token usage;
- provider metadata;
- latency;
- finish reason;
- error classification.

## 9. Structured outputs

Các step quan trọng phải dùng schema thay vì parse prose tùy tiện.

Ví dụ AngleSet:

```json
{
  "angles": [
    {
      "id": "...",
      "title": "...",
      "reader_value": "...",
      "originality": "...",
      "evidence_coverage": "...",
      "risk_flags": []
    }
  ]
}
```

Validate schema trước khi complete step.

## 10. Tool execution

External tools qua Tool Adapter chung.

Mỗi call lưu:

- tool key;
- request fingerprint;
- started/completed;
- result reference;
- latency;
- error;
- retry count.

Large raw outputs nên offload ra artifact/object store; model chỉ nhận summary/bounded excerpt cần thiết.

## 11. Context Guard

Trước mỗi model call:

- tính context estimate;
- loại duplicate context;
- ưu tiên locked evidence;
- giảm content-memory examples nếu quá budget;
- summarize tool outputs lớn;
- không cắt mất provenance IDs của evidence quan trọng.

## 12. Failure classes

Tối thiểu:

- `provider_transient`
- `provider_rate_limit`
- `provider_auth`
- `tool_transient`
- `tool_invalid_response`
- `schema_validation`
- `budget_exceeded`
- `insufficient_evidence`
- `quality_gate_failed`
- `approval_rejected`
- `publish_conflict`
- `internal_error`

Retry policy dựa theo class, không retry mọi lỗi.

## 13. Observability

Mỗi run có timeline:

```text
step
attempt
status
start/end
latency
model/tool
cost
evaluator result
human action
```

Dashboard V1 cần trả lời:

- run đang kẹt ở đâu;
- vì sao fail;
- tốn bao nhiêu;
- bước nào tốn nhiều nhất;
- model nào đang dùng;
- quality fail ở đâu.

## 14. Replay / regression

Harness hỗ trợ chế độ replay/eval:

- dùng frozen input fixtures;
- không publish;
- chạy candidate settings/model/prompt;
- ghi report so với baseline;
- không tự promote candidate.

## 15. Post-run hooks

Sau completed hoặc final approval:

- compute human edit delta;
- index final content vào Content Memory;
- tạo learning candidates;
- update run cost summary;
- schedule/attach measurement identity.

Post-run hook lỗi không được làm mất final content; phải retry độc lập.

## 16. Yêu cầu kiểm thử Harness

Phải có test cho:

- happy path;
- restart/resume;
- retry transient error;
- no retry auth error;
- approval pause/resume;
- artifact version invalidates approval;
- budget stop;
- duplicate publish prevention;
- duplicate ingest prevention;
- failed post-run hook recovery;
- bounded revise loop.
