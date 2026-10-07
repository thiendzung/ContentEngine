const COVERAGE_VI: Record<string, string> = {
  MISSING: "Thiếu nội dung",
  PLANNED: "Đã lên kế hoạch",
  IN_PROGRESS: "Đang sản xuất",
  PUBLISHED: "Đã xuất bản",
  NEEDS_UPDATE: "Cần cập nhật",
  WEAK: "Nội dung yếu",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  ANSWERED: "Đã trả lời",
  PARTIAL: "Đã có một phần",
  STALE: "Cần làm mới",
  COLLISION: "Có xung đột",
  MIXED: "Hỗn hợp",
};

const CONTENT_ROLE_VI: Record<string, string> = {
  primary: "Nội dung chính",
  pillar: "Nội dung trụ cột",
  cluster: "Cụm nội dung",
};

const NEED_ROLE_VI: Record<string, string> = {
  primary: "Nhu cầu chính",
  supporting: "Nhu cầu hỗ trợ",
};

const AUDIENCE_STAGE_VI: Record<string, string> = {
  curious: "Đang tò mò",
  exploring: "Đang tìm hiểu",
  first_time_buyer: "Người mua lần đầu",
  evaluating: "Đang đánh giá",
  ready_to_visit: "Sẵn sàng ghé xem",
  ready_to_inquire: "Sẵn sàng hỏi mua",
  owner: "Đã sở hữu",
};

const ANSWER_JOB_VI: Record<string, string> = {
  compare_options: "So sánh các lựa chọn",
  find_source: "Tìm nguồn phù hợp",
  understand_reason: "Hiểu lý do",
  learn_how: "Biết cách thực hiện",
  unresolved: "Chưa xác định",
  understand_value: "Hiểu giá trị",
  plan_budget: "Lập ngân sách",
  understand_customs: "Hiểu thủ tục hải quan",
  plan_shipping: "Lập kế hoạch vận chuyển",
  carry_home: "Mang tác phẩm về nhà",
  choose_size: "Chọn kích thước",
  verify_authenticity: "Kiểm tra tính xác thực",
  plan_transport: "Lập kế hoạch vận chuyển",
  fit_space: "Chọn tác phẩm phù hợp không gian",
  find_place_to_view: "Tìm nơi xem tác phẩm",
  care_for_art: "Bảo quản tác phẩm",
  understand_context: "Hiểu bối cảnh",
  negotiate_purchase: "Thương lượng khi mua",
  choose_with_confidence: "Chọn tác phẩm tự tin hơn",
  learn_art_making: "Tìm hiểu cách làm nghệ thuật",
  understand_artist_process: "Hiểu quy trình của họa sĩ",
};

const QUESTION_TYPE_VI: Record<string, string> = {
  what: "Là gì",
  why: "Vì sao",
  how: "Cách làm",
  where: "Ở đâu",
  compare: "So sánh",
  trust: "Xác thực / niềm tin",
  price: "Giá",
  logistics: "Vận chuyển",
  fit: "Mức độ phù hợp",
  visit: "Ghé xem",
  care: "Bảo quản",
  culture: "Văn hóa",
  other: "Khác",
};

const READINESS_VI: Record<string, string> = {
  READY_FOR_HUMAN_SELECTION: "Sẵn sàng để Người sáng lập chọn",
  RESEARCH_REQUIRED: "Cần nghiên cứu thêm",
  BLOCKED: "Đang bị chặn",
};

const ADMISSION_VI: Record<string, string> = {
  ADMITTED: "Có thể tiếp tục",
  RECONCILIATION_REQUIRED: "Cần xác nhận hợp nhất",
  BLOCKED_ROUTE_STALE: "Hướng xử lý đã thay đổi",
  BLOCKED_SELECTION_STALE: "Lựa chọn đã thay đổi",
  BLOCKED_OPPORTUNITY_STALE: "Cơ hội nội dung đã thay đổi",
  BLOCKED_TARGET_STALE: "Nội dung đích đã thay đổi",
  BLOCKED_ALREADY_MATERIALIZED: "Đã tạo bàn giao trước đó",
  BLOCKED_PRODUCTION_CONFLICT: "Có xung đột sản xuất",
};

const COVERAGE_REASON_VI: Record<string, string> = {
  no_content_or_selected_write_plan: "Chưa có nội dung hoặc kế hoạch viết được chọn.",
  selected_content_opportunity_exists: "Đã có cơ hội nội dung được chọn.",
  content_work_exists_without_current_published_completion:
    "Đã có công việc nội dung nhưng chưa có bản xuất bản hiện hành.",
  published_content_exists: "Đã có nội dung đang được xuất bản.",
  selected_update_or_refresh_targets_published_content:
    "Có kế hoạch cập nhật/làm mới nhắm tới nội dung đã xuất bản.",
  newer_unpublished_revision_exists:
    "Có bản sửa đổi mới hơn nhưng chưa được xuất bản.",
  unresolved_quality_failure_or_final_review_revision:
    "Còn lỗi chất lượng hoặc quyết định duyệt yêu cầu chỉnh sửa.",
  selected_update_target_ref_invalid:
    "Tham chiếu đích cập nhật không hợp lệ hoặc không còn khớp.",
  additional_weak_content_does_not_erase_published_coverage:
    "Có nội dung yếu bổ sung nhưng không xóa trạng thái độ phủ đã xuất bản.",
  weak_or_failed_revision_exists:
    "Tồn tại bản sửa đổi yếu hoặc chưa qua chất lượng.",
  duplicate_candidate_detected:
    "Phát hiện ứng viên nội dung trùng theo cùng nhu cầu/ngôn ngữ/ý định/câu hỏi.",
  same_primary_need_locale_intent_question:
    "Trùng nhu cầu chính, ngôn ngữ, ý định và câu hỏi chính.",
};

const PLANNING_REASON_VI: Record<string, string> = {
  canonical_need_supported: "Nhu cầu hiện có đủ bằng chứng hỗ trợ.",
  canonical_need_rejected: "Nhu cầu hiện đã bị bác bỏ.",
  canonical_need_evidence_insufficient: "Nhu cầu chưa có đủ bằng chứng.",
  coverage_semantics_insufficient: "Dữ liệu độ phủ chưa đủ để ra quyết định.",
  duplicate_plan_collision_requires_reconciliation:
    "Có kế hoạch trùng cần đối soát trước.",
  duplicate_selected_plans_require_reconciliation:
    "Có nhiều kế hoạch đã chọn cần đối soát.",
  matching_create_plan_or_work_exists:
    "Đã có kế hoạch hoặc công việc tạo mới tương ứng.",
  question_cluster_not_usable: "Cụm câu hỏi hiện chưa đủ điều kiện sử dụng.",
  search_lineage_missing: "Thiếu nguồn gốc tín hiệu tìm kiếm.",
  existing_plan_or_work_should_be_reused:
    "Nên sử dụng lại kế hoạch hoặc công việc hiện có.",
  repeated_search_signal: "Có tín hiệu tìm kiếm lặp lại.",
  single_search_signal: "Mới có một tín hiệu tìm kiếm.",
  no_search_signal: "Chưa có tín hiệu tìm kiếm.",
  right_to_win_unproven: "Lợi thế cạnh tranh của nội dung chưa được chứng minh.",
  existing_pillar_or_selected_plan_collision:
    "Nội dung trụ cột hoặc kế hoạch đã chọn đang xung đột.",
  founder_selection_required: "Cần Người sáng lập lựa chọn.",
  blocked_or_research_required_excluded_from_selection:
    "Phương án bị chặn hoặc cần nghiên cứu thêm nên không thể chọn.",
};

export function planningCoverageLabel(value: string): string {
  return COVERAGE_VI[value] ?? value;
}

export function planningContentRoleLabel(value: string): string {
  return CONTENT_ROLE_VI[value.toLowerCase()] ?? value;
}

export function planningNeedRoleLabel(value: string): string {
  return NEED_ROLE_VI[value.toLowerCase()] ?? value;
}

export function planningAudienceStageLabel(value: string): string {
  return AUDIENCE_STAGE_VI[value.toLowerCase()] ?? value;
}

export function planningAnswerJobLabel(value: string): string {
  return ANSWER_JOB_VI[value.toLowerCase()] ?? value;
}

export function planningQuestionTypeLabel(value: string): string {
  return QUESTION_TYPE_VI[value.toLowerCase()] ?? value;
}

export function planningReadinessLabel(value: string): string {
  return READINESS_VI[value] ?? value;
}

export function planningAdmissionLabel(value: string): string {
  return ADMISSION_VI[value] ?? "Đang bị chặn";
}

export function planningCoverageReasonLabel(value: string): string {
  return COVERAGE_REASON_VI[value] ?? value;
}

export function planningReasonLabel(value: string): string {
  if (PLANNING_REASON_VI[value]) return PLANNING_REASON_VI[value];
  if (value.startsWith("existing_content_action:")) {
    const action = value.split(":", 2)[1] ?? "";
    const actionLabels: Record<string, string> = {
      UPDATE: "cập nhật",
      REFRESH: "làm mới",
      MERGE: "hợp nhất",
      LINK_ONLY: "chỉ liên kết",
    };
    return `Đã có nội dung hiện có phù hợp với hướng ${actionLabels[action] ?? action}.`;
  }
  if (value.startsWith("canonical_need_status:")) {
    return "Trạng thái nhu cầu hiện chưa đủ điều kiện để tiếp tục.";
  }
  return value;
}

export function planningActorLabel(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized === "founder") return "Người sáng lập";
  if (normalized === "system") return "Hệ thống";
  return value;
}
