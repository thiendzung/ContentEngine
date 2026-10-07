import type { OperatorState, OperatorStatus, PreflightCheck } from "./journal-api";

export function operatorStatusLabel(status: OperatorStatus): string {
  const labels: Record<OperatorStatus, string> = {
    NOT_READY: "Chưa sẵn sàng",
    READY: "Sẵn sàng",
    QUEUED: "Đang chờ xử lý",
    RUNNING: "Đang thực hiện",
    AWAITING_APPROVAL: "Chờ Người sáng lập duyệt",
    BLOCKED: "Bị chặn",
    COMPLETE: "Hoàn thành",
  };
  return labels[status];
}

export function operatorWriterLaneStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "Chờ xếp hàng",
    queued: "Đang chờ tác nhân",
    running: "Đang viết",
    completed: "Đã có bản nháp",
    failed: "Lỗi — chỉ luồng này được thử lại",
  };
  return labels[status] ?? status;
}

export function operatorQualityStageLabel(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "final_gate_ready") return "Sẵn sàng duyệt cuối";
  if (normalized.includes("review")) return "Rà soát & chỉnh sửa";
  if (normalized.includes("audit")) return "Kiểm tra khẳng định";
  if (normalized.includes("source_copy")) return "Kiểm tra trùng nguồn";
  if (normalized.includes("reader_value")) return "Kiểm tra giá trị cho người đọc";
  if (normalized.includes("search_ai")) return "Kiểm tra SEO / AI";
  if (normalized.includes("failed")) return "Bị chặn";
  if (normalized.includes("queued")) return "Đang chờ tác nhân";
  if (normalized.includes("running")) return "Đang kiểm tra";
  return status;
}

export function operatorQualityResultLabel(value: string | null): string {
  if (!value) return "Đang chờ";
  const normalized = value.toLowerCase();
  if (normalized === "pass") return "Đạt";
  if (normalized === "warn") return "Cảnh báo";
  if (normalized === "fail") return "Không đạt";
  return value;
}

export function operatorReviewStateLabel(value: string): string {
  const labels: Record<string, string> = {
    PASS: "Đạt",
    WARN: "Cảnh báo",
    FAIL: "Không đạt",
    PENDING: "Đang chờ",
    CONSISTENT: "Nhất quán",
    INCONSISTENT: "Không nhất quán",
    NOT_PUBLISHED: "Chưa xuất bản",
    PUBLISHED: "Đã xuất bản",
    APPROVED_NOT_PUBLISHED: "Đã duyệt · chưa xuất bản",
    AWAITING_FOUNDER_APPROVAL: "Chờ duyệt cuối",
  };
  return labels[value] ?? value;
}

export function operatorNextActionLabel(value: string): string {
  const labels: Record<string, string> = {
    "Approved; publishing not authorized": "Đã duyệt; chưa cho phép xuất bản",
    "Awaiting Founder final approval": "Đang chờ Người sáng lập duyệt nội dung cuối",
    "Review current content": "Cần xem và duyệt nội dung hiện tại",
    "Current bytes are blocked by quality gates": "Nội dung hiện tại chưa qua kiểm tra chất lượng",
    "Resolve conflicting persisted bindings": "Cần xử lý dữ liệu liên kết không nhất quán",
    "Content is not ready for review": "Nội dung chưa sẵn sàng để duyệt",
    "Founder đã yêu cầu sửa": "Người sáng lập đã yêu cầu sửa",
    "Founder đã từ chối": "Người sáng lập đã từ chối",
    Published: "Đã xuất bản",
  };
  return labels[value] ?? value;
}

export function operatorQualityAuthorityLabel(value: string): string {
  const labels: Record<string, string> = {
    deterministic: "Luật cố định",
    upstream_gate: "Cổng kiểm tra trước",
    semantic_model: "Mô hình ngữ nghĩa",
  };
  return labels[value] ?? value;
}

export function operatorLocaleRoleLabel(value: string): string {
  const labels: Record<string, string> = {
    source: "Ngôn ngữ nguồn",
    translation: "Bản dịch",
  };
  return labels[value] ?? value;
}

export function operatorPhaseLabel(phase: string): string {
  const normalized = phase.toLowerCase();
  const labels: Record<string, string> = {
    intake: "Tiếp nhận",
    start_to_angle: "Nghiên cứu & tạo góc tiếp cận",
    angle: "Chọn góc tiếp cận",
    outline: "Lập dàn ý",
    final_review: "Duyệt cuối",
  };
  if (labels[normalized]) return labels[normalized];
  if (normalized.includes("angle")) return "Góc tiếp cận";
  if (normalized.includes("outline")) return "Dàn ý";
  if (normalized.includes("writer")) return "Soạn nội dung";
  if (normalized.includes("review")) return "Rà soát";
  return "Quy trình nội dung";
}

export function humanGateLabel(gate: OperatorState["human_gate"]): string {
  if (gate === "angle") return "Chọn góc tiếp cận";
  if (gate === "outline") return "Duyệt dàn ý";
  if (gate === "final_review") return "Duyệt nội dung cuối";
  return "Không có cổng duyệt đang chờ";
}

export function preflightLabel(key: string): string {
  const labels: Record<string, string> = {
    database_binding: "Kết nối cơ sở dữ liệu nội bộ",
    database: "Cơ sở dữ liệu",
    migration: "Phiên bản dữ liệu",
    test_database: "Cơ sở dữ liệu kiểm thử",
    codex_cli: "Codex CLI",
    antigravity_cli: "Antigravity",
    postgres_tools: "Công cụ sao lưu PostgreSQL",
    journal_research_serper: "Serper · tìm nguồn",
    journal_angle_settings: "Cấu hình mô hình góc tiếp cận",
    journal_angle_prompt: "Chỉ dẫn góc tiếp cận",
    journal_angle_recipe: "Công thức góc tiếp cận",
  };
  return labels[key] ?? key;
}

export function preflightDetail(check: PreflightCheck): string {
  if (check.status === "READY") return "Sẵn sàng";
  if (check.status === "OPTIONAL") return "Không bắt buộc";
  const details: Record<string, string> = {
    database_not_loopback: "Cơ sở dữ liệu không giới hạn ở máy cục bộ.",
    database_unavailable: "Không kết nối được cơ sở dữ liệu.",
    migration_state_unavailable: "Không đọc được trạng thái phiên bản dữ liệu.",
    migration_version_missing: "Thiếu thông tin phiên bản dữ liệu.",
    test_database_url_required: "Chưa cấu hình cơ sở dữ liệu kiểm thử.",
    "pg_dump+pg_restore_unavailable": "Thiếu công cụ sao lưu/khôi phục PostgreSQL.",
    operator_worker_serper_required: "Chưa cấu hình Serper cho tác nhân nghiên cứu.",
    journal_angle_active_settings_missing: "Chưa có cấu hình góc tiếp cận đang hoạt động.",
    journal_angle_active_settings_duplicate: "Có nhiều cấu hình góc tiếp cận hoạt động cùng lúc.",
    journal_angle_model_route_invalid: "Cấu hình định tuyến của mô hình góc tiếp cận không hợp lệ.",
    journal_angle_provider_not_allowed: "Góc tiếp cận hiện không được định tuyến qua Codex CLI.",
    journal_angle_model_unresolved: "Mô hình góc tiếp cận chưa được chọn chính thức.",
    active_prompt_missing: "Chưa có chỉ dẫn góc tiếp cận đang hoạt động.",
    active_prompt_duplicate: "Có nhiều chỉ dẫn góc tiếp cận hoạt động cùng lúc.",
  };
  if (details[check.detail]) return details[check.detail];
  if (check.detail.includes("active_recipe_missing")) {
    return "Chưa có công thức góc tiếp cận hoạt động cho ngôn ngữ nguồn được hỗ trợ.";
  }
  if (check.detail.includes("active_recipe_duplicate")) {
    return "Có nhiều công thức góc tiếp cận hoạt động cùng lúc.";
  }
  if (check.detail.includes("recipe_selector_mismatch")) {
    return "Công thức góc tiếp cận không khớp ngôn ngữ nguồn được hỗ trợ.";
  }
  return check.detail;
}

export function blockerAction(state: OperatorState): string {
  if (state.allowed_intents.includes("retry")) return "Có thể thử lại từ trạng thái hiện tại.";
  if (state.blocker_code === "operator_preflight_blocked") {
    return "Khắc phục kiểm tra sẵn sàng rồi tải lại trạng thái trước khi tiếp tục.";
  }
  return "Không tiếp tục tự động. Kiểm tra nguyên nhân rồi tải lại trạng thái.";
}
