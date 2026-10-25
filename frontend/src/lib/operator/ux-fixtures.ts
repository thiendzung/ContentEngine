import type {
  OperatorCaseView,
  OperatorCommandResult,
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
    view.state = {
      ...view.state,
      status: "BLOCKED",
      phase: "start_to_angle",
      primary_intent: "retry",
      allowed_intents: ["retry"],
      blocker_code: "fixture_evidence_missing",
      blocker_message: "Thiếu bằng chứng đủ tin cậy cho một khẳng định quan trọng.",
      last_checkpoint: "evidence_blocked",
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
