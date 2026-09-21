# 05 — HARNESS SPEC

## 1. Mục tiêu

Harness là lớp đảm bảo mỗi lần tạo nội dung diễn ra có cấu trúc, có checkpoint, có thể resume, đo được và tái hiện được.

Harness không quyết định nội dung viết gì; nó chỉ điều phối cách workflow chạy.

Không xây generic workflow platform trong V1.

## 2. Walking Skeleton trước production harness

CE01 phải có một đường thử mỏng dùng dữ liệu thật:

```text
Real Brief
+ Manual EvidenceSet
+ Manual OriginalityPack
+ Real Brand Examples
→ Angle
→ Outline
→ Draft
→ Basic Assertion Audit
→ Human Review
```

Đường này có thể chạy đơn giản trong dev. Nó dùng để kiểm chứng chất lượng content contract, không phải production runtime.

Production durability đầy đủ được xây ở CE03.

## 3. Run Graph V1 production

```text
CREATE_RUN
  ↓
DISCOVERY_RESEARCH / KNOWLEDGE_RECALL
  ↓
EVIDENCE_RESEARCH
  ↓
EVIDENCE_LOCK + ORIGINALITY_PACK
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
ASSERTION_AUDIT
  ↓
QUALITY_GATE
  ↓
WAIT_FINAL_APPROVAL
  ↓
CREATE_CONTENT_VERSION + PACKAGE
  ↓
PUBLISH (explicit action)
  ↓
COMPLETE
```

## 4. Bounded loops

Không có loop vô hạn.

Ví dụ:

- research expansion: tối đa N vòng theo budget;
- draft revise: mặc định tối đa 2 vòng;
- provider retry: theo error class;
- evaluator repair: bounded.

Khi hết budget/iteration:

- dừng;
- lưu root cause;
- trả trạng thái rõ;
- cho phép retry/modify/cancel.

## 5. Durable Job Queue

Production run không chạy cả bài trong một HTTP request dài.

Mỗi executable step được đưa vào durable job queue trong DB hoặc cơ chế có durability tương đương.

Job tối thiểu có:

- `job_id`;
- `run_id`;
- `step_run_id`;
- `status`;
- `available_at`;
- `attempt`;
- `lease_owner` nullable;
- `lease_expires_at` nullable;
- `dedupe_key`;
- timestamps.

## 6. Worker lease + heartbeat

Worker flow:

```text
claim available job atomically
→ set lease
→ execute
→ heartbeat while long-running
→ persist artifact/result
→ commit state
→ mark job done
```

Nếu worker chết hoặc mất kết nối:

- lease hết hạn;
- job được reclaim;
- system resume từ durable state;
- không coi `running` cũ là bằng chứng side effect đã thất bại.

## 7. Checkpoint contract

Checkpoint tạo sau mỗi step hoàn thành và trước mỗi human approval gate.

Tối thiểu giữ:

- run state;
- step outputs/artifact IDs;
- settings snapshot ID;
- evidence set ID/version;
- context manifest refs;
- model/tool ledger refs;
- pending approval;
- retry counters.

Không lưu secret/provider session token.

## 8. Resume semantics

Khi service restart:

1. load durable state/checkpoint;
2. kiểm tra step complete;
3. không chạy lại side effect đã xác nhận;
4. reclaim job có lease hết hạn;
5. nếu external call có kết quả không rõ, reconciliation trước retry;
6. tiếp tục từ step phù hợp.

## 9. Side-effect outbox/reconciliation

Side effect quan trọng như WordPress publish phải có durable intent/outbox hoặc cơ chế tương đương.

```text
persist publish intent + idempotency key
→ commit DB
→ worker calls WordPress
→ reconcile external result
→ persist external ID/revision
→ complete intent
```

Nếu worker chết sau khi WordPress nhận request nhưng trước khi DB ghi kết quả, lần sau phải hỏi/reconcile trước khi gửi lại.

## 10. Approval gate

Approval là state chính thức.

Actions:

- approve;
- reject;
- request_changes.

Mỗi decision lưu actor/time/artifact version/comment.

Artifact thay đổi sau approval → approval cũ không tự áp dụng.

## 11. Budget contract

Budget cấu hình theo run và step:

- max model calls;
- max tool calls;
- max context estimate;
- max output tokens;
- max estimated cost;
- max wall-clock duration;
- max research sources;
- max revise loops.

Budget stop phải có lý do explicit.

## 12. Model call adapter

```text
ModelRouter.resolve(task, project, locale, settings)
    ↓
ModelClient.generate(request)
```

Request chứa:

- task key;
- prompt version;
- `context_manifest_id`;
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

## 13. ContextManifest

Trước model call quan trọng:

1. build bounded context;
2. dedupe;
3. lưu IDs/hashes của context;
4. tạo ContextManifest bất biến;
5. model call tham chiếu manifest đó.

Mục tiêu: khi output tốt/xấu, biết chính xác model đã nhìn thấy gì.

## 14. Structured outputs

Step quan trọng dùng schema thay vì parse prose tùy tiện.

Ví dụ AngleSet:

```json
{
  "angles": [
    {
      "id": "...",
      "title": "...",
      "reader_value": "...",
      "reader_transformation": "...",
      "originality": "...",
      "evidence_coverage": "...",
      "risk_flags": []
    }
  ]
}
```

Validate schema trước complete step.

## 15. Tool execution

External tools qua Tool Adapter chung.

Mỗi call lưu:

- tool key;
- request fingerprint;
- started/completed;
- result reference;
- latency;
- error;
- retry count.

Large output offload ra artifact/object store; model chỉ nhận phần bounded cần thiết.

## 16. Context Guard

Trước mỗi model call:

- tính context estimate;
- loại duplicate;
- ưu tiên locked EvidenceSet;
- ưu tiên OriginalityPack;
- giảm Content Memory/Golden examples trước khi cắt evidence;
- summarize tool output lớn;
- giữ provenance ID của evidence quan trọng.

## 17. Failure classes

Tối thiểu:

- `provider_transient`
- `provider_rate_limit`
- `provider_auth`
- `tool_transient`
- `tool_invalid_response`
- `schema_validation`
- `budget_exceeded`
- `insufficient_evidence`
- `unsupported_assertion`
- `quality_gate_failed`
- `approval_rejected`
- `publish_conflict`
- `lease_lost`
- `internal_error`

Retry dựa theo class.

## 18. Observability

Mỗi run có timeline:

```text
step
attempt
job/lease
status
start/end
latency
model/tool
cost
evaluator result
human action
```

Dashboard V1 cần trả lời:

- run kẹt ở đâu;
- vì sao fail;
- tốn bao nhiêu;
- bước nào tốn nhiều nhất;
- model nào dùng;
- quality fail ở đâu.

## 19. Replay / regression

Harness hỗ trợ replay/eval:

- frozen inputs/context fixtures;
- không publish;
- candidate settings/model/prompt;
- report candidate vs baseline;
- không tự promote.

## 20. Post-run jobs

Sau final approval/completed:

- compute human edit delta;
- index ContentVersion vào Content Memory;
- tạo learning candidates;
- update cost summary;
- attach measurement identity.

Các việc này chạy như durable jobs riêng. Lỗi không làm mất final content.

## 21. Yêu cầu kiểm thử Harness

Phải có test cho:

- happy path;
- restart/resume;
- worker lease expiry/reclaim;
- retry transient error;
- no retry auth error;
- approval pause/resume;
- artifact version invalidates approval;
- budget stop;
- duplicate publish prevention;
- duplicate ingest prevention;
- ambiguous side-effect reconciliation;
- failed post-run job recovery;
- bounded revise loop;
- context manifest reproducibility.

## 22. AU-02 Local Agent Bridge contract

AU-02 is a thin control-plane layer over the existing Harness. It does not add a second scheduler, queue, workflow engine, approval store, or telemetry table.

Execution boundary:

1. an immutable AU-01 `ExecutionPlan` is authorized against the run's immutable `SettingsSnapshot`;
2. the exact plan Artifact is bound to one `StepRun`;
3. human-gated plans must pass the existing canonical approval pause/resume flow before a Job can be queued;
4. claim returns the exact plan/settings/task/worker contract to the local worker;
5. heartbeat/reclaim reuse the existing Job lease lifecycle and cannot exceed the plan deadline;
6. complete/fail re-authorizes the exact plan and canonical run state before changing durable state;
7. completion outputs must belong to the exact run/step, match expected types, have valid content hashes, be produced after execution start, and be the latest version of that output type;
8. worker completion creates a review request, not an auto-pass;
9. an independent reviewer must match `ExecutionPlan.reviewer`, differ from the worker, and return every required check;
10. review request/result semantics are reconstructed from canonical Job/StepRun/ExecutionPlan/completion lineage before auto-next;
11. auto-next creates only the next pending StepRun. It does not enqueue that step until that step has its own authorized ExecutionPlan.

Approval provenance is stronger than the presence of one `Approval` row. A human-gated execution requires:

- an earlier immutable checkpoint showing `pending_approval` for the exact step + ExecutionPlan Artifact;
- an exact approved `Approval` bound to that Artifact;
- a later canonical checkpoint containing that Approval;
- a non-worker approval actor;
- the run back in executable `running` state.

Retry:

- transient retry creates a new StepRun attempt and a new ExecutionPlan Artifact;
- a human-gated retry requires fresh approval for the retry plan;
- an expired lease can be reclaimed only inside the plan's bounded attempts;
- completion/failure write immutable receipts and a checkpoint for restart/recovery.

Budget enforcement:

- AU-02 directly enforces durable ModelCall/ToolCall/output-token/estimated-cost/wall-clock usage already observable in the Harness;
- AU-01 counters that are not yet durably observable at this boundary (`max_context_estimate`, `max_research_sources`, `max_revise_loops`) fail closed rather than trusting worker self-reporting;
- adding durable ledgers for those counters is a separate hardening task, not permission to infer or self-report them.

Telemetry:

- root worker/subagent hierarchy reuses `DelegationExecution`;
- safe bridge telemetry is allowlisted;
- prompts, raw provider payloads, secrets, environment dumps and chain-of-thought are not bridge telemetry.

Provider/transport boundary:

- this contract is provider-neutral and transport-neutral;
- AU-02 does not activate Antigravity;
- no unauthenticated public bridge endpoint is introduced;
- an app-specific/local transport adapter must preserve these service semantics and receive its own review before activation.

### AU-02 output-integrity boundary

A completed output must be produced **strictly after** the bound StepRun starts. Equality with `StepRun.started_at` is not sufficient provenance and fails closed.

AU-02 currently verifies Artifact content hashes only for canonical `content_json` payloads. The base Artifact model also permits an `external_ref` without `content_json`, but the repository does not yet define a canonical resolver/hash-verification contract for external objects.

Therefore external-only output Artifacts are not accepted by AU-02 execution completion yet; they fail closed with `agent_bridge_external_output_hash_unverifiable`. Supporting external-object outputs later requires a reviewed canonical external-object verifier rather than trusting an arbitrary stored hash.

