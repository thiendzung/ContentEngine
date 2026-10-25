import type {
  OperatorCaseHistory,
  OperatorCaseView,
  OperatorCommandResult,
  OperatorDecisionResult,
  ReviewCaseDetail,
} from "./journal-api";

export const UX_FIXTURE_PREFIX = "ux-fixture-";

export type OperatorUxFixtureState =
  | "ready"
  | "queued"
  | "running"
  | "blocked"
  | "approval"
  | "complete"
  | "error"
  | "stale"
  | "empty";

const CASE_ID = "11111111-1111-4111-8111-111111111111";
const VARIANT_ID = "22222222-2222-4222-8222-222222222222";
const ARTIFACT_ID = "33333333-3333-4333-8333-333333333333";
const FINAL_ARTIFACT_ID = "44444444-4444-4444-8444-444444444444";

function fixtureEnabled(): boolean {
  return process.env.NEXT_PUBLIC_UX_FIXTURES === "1";
}

export function isOperatorUxFixtureCase(caseId: string): boolean {
  return fixtureEnabled() && caseId.startsWith(UX_FIXTURE_PREFIX);
}

export function operatorUxFixtureState(caseId: string): OperatorUxFixtureState | null {
  if (!isOperatorUxFixtureCase(caseId)) return null;
  const value = caseId.slice(UX_FIXTURE_PREFIX.length);
  const states: OperatorUxFixtureState[] = [
    "ready",
    "queued",
    "running",
    "blocked",
    "approval",
    "complete",
    "error",
    "stale",
    "empty",
  ];
  return states.includes(value as OperatorUxFixtureState)
    ? (value as OperatorUxFixtureState)
    : null;
}

export function noteOperatorUxFixtureRequest(caseId: string): void {
  if (typeof globalThis === "undefined") return;
  const root = globalThis as typeof globalThis & {
    __CE_UX_FIXTURE_REQUESTS__?: Record<string, number>;
  };
  root.__CE_UX_FIXTURE_REQUESTS__ ??= {};
  root.__CE_UX_FIXTURE_REQUESTS__[caseId] =
    (root.__CE_UX_FIXTURE_REQUESTS__[caseId] ?? 0) + 1;
}

function baseView(): OperatorCaseView {
  return {
    content_case_id: CASE_ID,
    question: "Lần đầu đến Hà Nội nên dành 2 ngày như thế nào?",
    reader: "Khách quốc tế lần đầu đến Hà Nội",
    situation: "Có hai ngày trọn vẹn và muốn ưu tiên trải nghiệm văn hóa địa phương.",
    need: "Một lịch trình rõ ràng, ít di chuyển vòng và không chạy theo checklist.",
    intent: "Lập kế hoạch chuyến đi",
    promise: "Giúp người đọc biết nên đi đâu, theo thứ tự nào và vì sao.",
    content_role: "pillar",
    coverage_requirements: [
      {
        id: "coverage-1",
        requirement: "Có lịch trình sáng / chiều / tối và phương án khi trời mưa.",
      },
    ],
    state: {
      content_case_id: CASE_ID,
      state_version: "ux-fixture-v1",
      status: "READY",
      phase: "intake",
      primary_intent: "start",
      allowed_intents: ["start"],
      human_gate: null,
      current_run_id: null,
      current_step_run_id: null,
      current_worker: null,
      last_checkpoint: null,
      quality_summary: null,
      blocker_code: null,
      blocker_message: null,
    },
    intake: {
      source_locale: "vi-VN",
      research_country: "VN",
      required_locales: [
        { locale: "vi-VN", role: "source" },
        { locale: "en", role: "translation" },
      ],
    },
    pending_gate: null,
    writer_lanes: [],
    quality_lanes: [],
  };
}

function angleApprovalView(): OperatorCaseView {
  const view = baseView();
  view.state = {
    ...view.state,
    status: "AWAITING_APPROVAL",
    phase: "angle",
    primary_intent: null,
    allowed_intents: [],
    human_gate: "angle",
    current_run_id: "55555555-5555-4555-8555-555555555555",
    current_step_run_id: "66666666-6666-4666-8666-666666666666",
    last_checkpoint: "angle_ready",
  };
  view.pending_gate = {
    type: "angle",
    artifact: {
      id: ARTIFACT_ID,
      version: 1,
      content_hash: "a".repeat(64),
    },
    candidates: [
      {
        angle_id: "angle-local-first",
        candidate_hash: "b".repeat(64),
        working_title: "Hai ngày Hà Nội theo nhịp sống địa phương",
        reader_problem: "Quá nhiều danh sách điểm đến nhưng khó biết nên ưu tiên gì.",
        central_question: "Hai ngày ở Hà Nội nên sắp xếp thế nào để vừa đủ mà không vội?",
        core_promise: "Một tuyến đi bộ gọn, có khoảng nghỉ và lý do cho từng điểm dừng.",
        point_of_view: "Ưu tiên nhịp điệu chuyến đi thay vì số lượng địa điểm.",
        why_now: "Phù hợp với khách lần đầu muốn trải nghiệm văn hóa thay vì chạy checklist.",
        evidence_refs: ["fixture:evidence:1"],
        originality_refs: ["fixture:motgu:1"],
        excluded_claims: ["Không khẳng định đây là lịch trình duy nhất đúng."],
        risks: ["Giờ mở cửa có thể thay đổi."],
        confidence: 0.86,
        locale: "vi-VN",
        coverage: [
          {
            requirement_id: "coverage-1",
            requirement: "Có lịch trình sáng / chiều / tối và phương án khi trời mưa.",
            status: "covered",
            rationale: "Góc tiếp cận dành chỗ cho phương án thay thế theo thời tiết.",
          },
        ],
      },
    ],
  };
  return view;
}

export function getOperatorUxHistoryFixture(
  caseId: string,
): OperatorCaseHistory | null {
  const state = operatorUxFixtureState(caseId);
  if (!state) return null;

  const baseEvents: OperatorCaseHistory["events"] = [
    {
      id: "artifact:fixture-intake",
      at: "2026-10-25T05:59:58Z",
      kind: "artifact",
      stage: "journal_intake",
      status: "created",
      locale: "vi-VN",
      attempt: null,
      run_id: "55555555-5555-4555-8555-555555555555",
      step_run_id: null,
      artifact_id: "12121212-1212-4212-8212-121212121212",
      artifact_type: "journal_intake",
      artifact_version: 1,
      artifact_hash: "d".repeat(64),
      error_code: null,
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: null,
      retry_count: null,
      resolved_action_key: null,
    },
    {
      id: "step:fixture-intake",
      at: "2026-10-25T05:59:59Z",
      kind: "step",
      stage: "intake",
      status: "completed",
      locale: "vi-VN",
      attempt: 1,
      run_id: "55555555-5555-4555-8555-555555555555",
      step_run_id: "13131313-1313-4313-8313-131313131313",
      artifact_id: null,
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: null,
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: 120,
      retry_count: null,
      resolved_action_key: null,
    },
    {
      id: "quality:fixture-intake",
      at: "2026-10-25T05:59:59.500Z",
      kind: "quality",
      stage: "intake_contract",
      status: "pass",
      locale: "vi-VN",
      attempt: null,
      run_id: "55555555-5555-4555-8555-555555555555",
      step_run_id: null,
      artifact_id: "12121212-1212-4212-8212-121212121212",
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: null,
      decision: null,
      result: "pass",
      evaluator_key: "intake_contract",
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: null,
      retry_count: null,
      resolved_action_key: null,
    },
    {
      id: "command:fixture-create",
      at: "2026-10-25T06:00:00Z",
      kind: "command",
      stage: "create",
      status: "completed",
      locale: "vi-VN",
      attempt: null,
      run_id: null,
      step_run_id: null,
      artifact_id: null,
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: null,
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: null,
      retry_count: null,
      resolved_action_key: "create_case",
    },
    {
      id: "run:fixture-bootstrap",
      at: "2026-10-25T06:00:01Z",
      kind: "run",
      stage: "intake",
      status: "completed",
      locale: "vi-VN",
      attempt: null,
      run_id: "55555555-5555-4555-8555-555555555555",
      step_run_id: null,
      artifact_id: null,
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: null,
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: 240,
      retry_count: null,
      resolved_action_key: null,
    },
  ];

  if (state === "queued" || state === "running") {
    baseEvents.push({
      id: "step:fixture-research",
      at: "2026-10-25T06:01:00Z",
      kind: "step",
      stage: "start_to_angle",
      status: state === "queued" ? "pending" : "running",
      locale: "vi-VN",
      attempt: 1,
      run_id: "77777777-7777-4777-8777-777777777777",
      step_run_id: "88888888-8888-4888-8888-888888888888",
      artifact_id: null,
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: null,
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: null,
      retry_count: null,
      resolved_action_key: null,
    });
  }

  if (state === "blocked") {
    baseEvents.push(
      {
        id: "research-summary:fixture-blocked",
        at: "2026-10-25T06:01:58Z",
        kind: "research",
        stage: "research_summary",
        status: "completed",
        locale: "vi-VN",
        attempt: null,
        run_id: "77777777-7777-4777-8777-777777777777",
        step_run_id: "88888888-8888-4888-8888-888888888888",
        artifact_id: "14141414-1414-4414-8414-141414141414",
        artifact_type: "research_trace",
        artifact_version: 1,
        artifact_hash: "e".repeat(64),
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: null,
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
        reason_code: "exa_sufficient",
        provider_call_count: 5,
        pages_read: 3,
      },
      {
        id: "research-decision:fixture-serper",
        at: "2026-10-25T06:01:58Z",
        kind: "research",
        stage: "provider_decision",
        status: "called",
        locale: "vi-VN",
        attempt: null,
        run_id: "77777777-7777-4777-8777-777777777777",
        step_run_id: "88888888-8888-4888-8888-888888888888",
        artifact_id: "14141414-1414-4414-8414-141414141414",
        artifact_type: "research_trace",
        artifact_version: 1,
        artifact_hash: "e".repeat(64),
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: "serper",
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
        reason_code: "default_google_discovery",
        provider_call_count: null,
        pages_read: null,
      },
      {
        id: "research-decision:fixture-exa",
        at: "2026-10-25T06:01:58Z",
        kind: "research",
        stage: "provider_decision",
        status: "called",
        locale: "vi-VN",
        attempt: null,
        run_id: "77777777-7777-4777-8777-777777777777",
        step_run_id: "88888888-8888-4888-8888-888888888888",
        artifact_id: "14141414-1414-4414-8414-141414141414",
        artifact_type: "research_trace",
        artifact_version: 1,
        artifact_hash: "e".repeat(64),
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: "exa",
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
        reason_code: "evidence_candidate_authority_recovery",
        provider_call_count: null,
        pages_read: null,
      },
      {
        id: "research-decision:fixture-tavily",
        at: "2026-10-25T06:01:58Z",
        kind: "research",
        stage: "provider_decision",
        status: "skipped",
        locale: "vi-VN",
        attempt: null,
        run_id: "77777777-7777-4777-8777-777777777777",
        step_run_id: "88888888-8888-4888-8888-888888888888",
        artifact_id: "14141414-1414-4414-8414-141414141414",
        artifact_type: "research_trace",
        artifact_version: 1,
        artifact_hash: "e".repeat(64),
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: "tavily",
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
        reason_code: "exa_sufficient",
        provider_call_count: null,
        pages_read: null,
      },
      {
      id: "step:fixture-blocked",
      at: "2026-10-25T06:02:00Z",
      kind: "step",
      stage: "coverage_support_depth",
      status: "failed",
      locale: "vi-VN",
      attempt: 1,
      run_id: "77777777-7777-4777-8777-777777777777",
      step_run_id: "88888888-8888-4888-8888-888888888888",
      artifact_id: null,
      artifact_type: null,
      artifact_version: null,
      artifact_hash: null,
      error_code: "insufficient_support",
      decision: null,
      result: null,
      evaluator_key: null,
      provider: null,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost: null,
      latency_ms: 820,
      retry_count: null,
      resolved_action_key: null,
      },
    );
  }

  if (state === "approval") {
    baseEvents.push(
      {
        id: "artifact:fixture-angle",
        at: "2026-10-25T06:03:00Z",
        kind: "artifact",
        stage: "angle_candidates",
        status: "created",
        locale: "vi-VN",
        attempt: null,
        run_id: "55555555-5555-4555-8555-555555555555",
        step_run_id: "66666666-6666-4666-8666-666666666666",
        artifact_id: ARTIFACT_ID,
        artifact_type: "angle_candidates",
        artifact_version: 1,
        artifact_hash: "a".repeat(64),
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: null,
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
      },
      {
        id: "run:fixture-waiting",
        at: "2026-10-25T06:03:01Z",
        kind: "run",
        stage: "angle",
        status: "waiting_approval",
        locale: "vi-VN",
        attempt: null,
        run_id: "55555555-5555-4555-8555-555555555555",
        step_run_id: null,
        artifact_id: null,
        artifact_type: null,
        artifact_version: null,
        artifact_hash: null,
        error_code: null,
        decision: null,
        result: null,
        evaluator_key: null,
        provider: null,
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
      },
    );
  }

  if (state === "complete") {
    baseEvents.push(
      {
        id: "quality:fixture-final",
        at: "2026-10-25T06:04:00Z",
        kind: "quality",
        stage: "search_ai",
        status: "pass",
        locale: "vi-VN",
        attempt: null,
        run_id: "55555555-5555-4555-8555-555555555555",
        step_run_id: null,
        artifact_id: FINAL_ARTIFACT_ID,
        artifact_type: null,
        artifact_version: null,
        artifact_hash: null,
        error_code: null,
        decision: null,
        result: "pass",
        evaluator_key: "search_ai",
        provider: null,
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
      },
      {
        id: "approval:fixture-final",
        at: "2026-10-25T06:05:00Z",
        kind: "approval",
        stage: "final_review",
        status: "approved",
        locale: "vi-VN",
        attempt: null,
        run_id: "55555555-5555-4555-8555-555555555555",
        step_run_id: null,
        artifact_id: FINAL_ARTIFACT_ID,
        artifact_type: null,
        artifact_version: null,
        artifact_hash: null,
        error_code: null,
        decision: "approved",
        result: null,
        evaluator_key: null,
        provider: null,
        model: null,
        input_tokens: null,
        output_tokens: null,
        cost: null,
        latency_ms: null,
        retry_count: null,
        resolved_action_key: null,
      },
    );
  }

  return {
    schema_version: 1,
    content_case_id: CASE_ID,
    generated_at: "2026-10-25T06:06:00Z",
    truncated: false,
    summary: {
      event_count: baseEvents.length,
      run_count: baseEvents.filter((event) => event.kind === "run").length,
      step_count: baseEvents.filter((event) => event.kind === "step").length,
      approval_count: baseEvents.filter((event) => event.kind === "approval").length,
      quality_count: baseEvents.filter((event) => event.kind === "quality").length,
      failed_count: baseEvents.filter((event) =>
        ["failed", "rejected", "cancelled", "fail"].includes(event.status),
      ).length,
      warning_count: baseEvents.filter((event) => event.status === "warn").length,
    },
    events: baseEvents,
  };
}

export function getOperatorUxFixture(caseId: string): OperatorCaseView | null {
  const state = operatorUxFixtureState(caseId);
  if (!state || state === "error") return null;
  if (state === "approval") return angleApprovalView();

  const view = baseView();
  if (state === "queued") {
    view.state = {
      ...view.state,
      status: "QUEUED",
      phase: "start_to_angle",
      primary_intent: null,
      allowed_intents: [],
      current_run_id: "77777777-7777-4777-8777-777777777777",
      current_step_run_id: "88888888-8888-4888-8888-888888888888",
      last_checkpoint: "queued",
    };
  } else if (state === "running") {
    view.state = {
      ...view.state,
      status: "RUNNING",
      phase: "start_to_angle",
      primary_intent: null,
      allowed_intents: [],
      current_run_id: "77777777-7777-4777-8777-777777777777",
      current_step_run_id: "88888888-8888-4888-8888-888888888888",
      current_worker: "fixture-worker",
      last_checkpoint: "research_running",
    };
  } else if (state === "blocked") {
    view.question = "What does a certificate of authenticity actually prove?";
    view.reader = "Người lần đầu mua tranh gốc";
    view.situation = "Đang kiểm tra giấy tờ đi kèm tác phẩm trước khi mua";
    view.need = "Hiểu COA chứng minh được gì, không chứng minh được gì và cần kiểm tra thêm tài liệu nào";
    view.intent = "learn";
    view.promise = "Giải thích giới hạn của COA và đưa checklist kiểm tra thực tế, không hứa quá mức về tính xác thực hay pháp lý.";
    view.coverage_requirements = [
      {
        id: "coverage-1",
        requirement: "Ai cấp chứng nhận, và vì sao danh tính / thẩm quyền của bên cấp quan trọng?",
      },
      {
        id: "coverage-2",
        requirement: "Chứng nhận khác provenance và hóa đơn như thế nào?",
      },
      {
        id: "coverage-3",
        requirement: "QR code hoặc registry entry có tự nó chứng minh tác phẩm là thật không?",
      },
      {
        id: "coverage-4",
        requirement: "Người mua lần đầu nên hỏi gì trước khi dựa vào các giấy tờ?",
      },
      {
        id: "coverage-5",
        requirement: "COA không tự động chứng minh điều gì về hải quan, thuế, quyền sở hữu, giá trị, bản quyền hoặc tính xác thực?",
      },
    ];
    view.state = {
      ...view.state,
      status: "BLOCKED",
      phase: "start_to_angle",
      primary_intent: "retry",
      allowed_intents: ["retry"],
      blocker_code: "insufficient_support",
      blocker_message: (
        "Chưa đủ độ sâu bằng chứng để tiếp tục tới Góc tiếp cận. "
        + "Thiếu nguồn xác định bên cấp chứng nhận và phân biệt hóa đơn với chứng nhận / provenance."
      ),
      last_checkpoint: "coverage_support_blocked",
    };
  } else if (state === "complete") {
    view.state = {
      ...view.state,
      status: "COMPLETE",
      phase: "final_review",
      primary_intent: null,
      allowed_intents: [],
      last_checkpoint: "final_approved",
      quality_summary: { passed: 12, warned: 1, failed: 0 },
    };
  } else if (state === "empty") {
    view.question = "Chưa có nội dung để tiếp tục";
    view.reader = "—";
    view.situation = "—";
    view.need = "—";
    view.intent = "—";
    view.promise = "—";
    view.coverage_requirements = [];
    view.state = {
      ...view.state,
      status: "NOT_READY",
      phase: "intake",
      primary_intent: null,
      allowed_intents: [],
      blocker_code: "fixture_empty",
      blocker_message: "Chưa có dữ liệu đủ để bắt đầu.",
    };
    view.intake.required_locales = [{ locale: "vi-VN", role: "source" }];
  }
  return view;
}

export function getReviewUxFixture(caseId: string): ReviewCaseDetail | null {
  if (operatorUxFixtureState(caseId) !== "complete") return null;
  return {
    id: CASE_ID,
    status: "complete",
    content_type: "journal",
    opportunity_question: "Lần đầu đến Hà Nội nên dành 2 ngày như thế nào?",
    opportunity_decision: "CREATE",
    reader_before: "Chưa biết ưu tiên điểm nào.",
    reader_after: "Có lịch trình hai ngày rõ ràng và biết vì sao từng điểm đáng đi.",
    content_hypothesis: "Một lịch trình theo nhịp sống địa phương giúp giảm quá tải lựa chọn.",
    angle: null,
    outline: null,
    locales: [
      {
        locale_variant_id: VARIANT_ID,
        locale: "vi-VN",
        locale_status: "approved",
        content_item_id: "99999999-9999-4999-8999-999999999999",
        canonical_key: "hanoi-2-day-local-first",
        content_item_status: "approved",
        content_version_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        content_version_no: 1,
        content_version_status: "approved",
        final_content: {
          id: FINAL_ARTIFACT_ID,
          artifact_type: "final_content",
          version: 1,
          content_hash: "c".repeat(64),
          locale: "vi-VN",
        },
        article: {
          title: "Hai ngày Hà Nội theo nhịp sống địa phương",
          standfirst: "Một lịch trình gọn cho người lần đầu đến Hà Nội.",
          lead_markdown: "Đi ít hơn nhưng hiểu thành phố nhiều hơn.",
          sections: [
            {
              section_id: "day-1",
              heading: "Ngày 1 · Phố cũ và nhịp sống quanh hồ",
              body_markdown: "Bắt đầu chậm, đi bộ và dành thời gian quan sát.",
            },
          ],
          closing_markdown: "Giữ một khoảng trống để thay đổi theo thời tiết và năng lượng.",
        },
        final_approval: {
          id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          decision: "approved",
          actor_id: "founder",
          comment: null,
        },
        assertion_audit: {
          artifact: null,
          quality_evaluation_id: null,
          result: "PASS",
          critical_unsupported_count: 0,
          critical_contradicted_count: 0,
          unsupported_count: 0,
          contradicted_count: 0,
        },
        source_copy: {
          artifact: null,
          quality_evaluation_id: null,
          result: "PASS",
          fail_count: 0,
          warn_count: 0,
          finding_count: 0,
          max_overlap_tokens: 0,
          findings: [],
        },
        provenance: {
          writer_run_id: null,
          writer_run_status: "completed",
          source_draft: null,
          final_content: {
            id: FINAL_ARTIFACT_ID,
            artifact_type: "final_content",
            version: 1,
            content_hash: "c".repeat(64),
            locale: "vi-VN",
          },
          content_version_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          content_version_no: 1,
          content_version_status: "approved",
        },
        quality_state: "PASS",
        publication_state: "APPROVED_NOT_PUBLISHED",
        consistency_state: "CONSISTENT",
        issues: [],
        next_action: "APPROVED_NOT_PUBLISHED",
        next_action_label: "Approved; publishing not authorized",
      },
    ],
    quality_state: "PASS",
    publication_state: "APPROVED_NOT_PUBLISHED",
    consistency_state: "CONSISTENT",
    issues: [],
    next_action: "APPROVED_NOT_PUBLISHED",
    next_action_label: "Approved; publishing not authorized",
  };
}

export function getOperatorUxCommandResult(
  caseId: string,
  intent: string,
): OperatorCommandResult | null {
  if (!isOperatorUxFixtureCase(caseId)) return null;
  return {
    command_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    content_case_id: CASE_ID,
    intent: intent as OperatorCommandResult["intent"],
    status: "completed",
    state_before: "ux-fixture-v1",
    state_after: "ux-fixture-v2",
    job_id: null,
    replayed: false,
  };
}


export function getOperatorUxDecisionResult(
  caseId: string,
  scope: OperatorDecisionResult["scope"],
): OperatorDecisionResult | null {
  if (!isOperatorUxFixtureCase(caseId)) return null;
  return {
    command_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    content_case_id: CASE_ID,
    scope,
    decision: "approved",
    approval_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    state_before: "ux-fixture-v1",
    state_after: "ux-fixture-v2",
    replayed: false,
  };
}
