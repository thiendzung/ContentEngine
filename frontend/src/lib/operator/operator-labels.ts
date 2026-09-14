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
  };
  return labels[key] ?? key;
}

export function preflightDetail(check: PreflightCheck): string {
  if (check.status === "READY") return "Sẵn sàng";
  if (check.status === "OPTIONAL") return "Không bắt buộc";
  const details: Record<string, string> = {
    database_not_loopback: "Cơ sở dữ liệu không giới hạn ở máy cục bộ.",
    database_unavailable: "Không kết nối được cơ sở dữ liệu.",
    migration_state_unavailable: "Không đọc được trạng thái migration.",
    migration_version_missing: "Thiếu thông tin phiên bản migration.",
    test_database_url_required: "Chưa cấu hình cơ sở dữ liệu kiểm thử.",
    "pg_dump+pg_restore_unavailable": "Thiếu công cụ sao lưu/khôi phục PostgreSQL.",
  };
  return details[check.detail] ?? check.detail;
}

export function blockerAction(state: OperatorState): string {
  if (state.allowed_intents.includes("retry")) return "Có thể thử lại từ trạng thái hiện tại.";
  if (state.blocker_code === "operator_preflight_blocked") {
    return "Khắc phục preflight rồi tải lại trạng thái trước khi tiếp tục.";
  }
  return "Không tiếp tục tự động. Kiểm tra nguyên nhân rồi tải lại trạng thái.";
}
