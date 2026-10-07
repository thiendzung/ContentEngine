import { uiDecisionLabel, uiPriorityLabel } from "./content";
import {
  learningActionLabel,
  learningSourceKindLabel,
  learningStatusLabel,
  learningTargetLabel,
} from "./learning";
import { uiStatusLabel } from "./status";

const EVENT_KIND_VI: Record<string, string> = {
  signal_captured: "Ghi nhận tín hiệu",
  need_reviewed: "Duyệt nhu cầu",
  insight_reviewed: "Duyệt nhận định khách hàng",
  content_opportunity_created: "Tạo cơ hội nội dung",
  content_opportunity_selected: "Chọn cơ hội nội dung",
  content_item_created: "Tạo nội dung",
  content_version_created: "Tạo phiên bản nội dung",
  content_run_started: "Bắt đầu lượt sản xuất",
  content_run_completed: "Hoàn tất lượt sản xuất",
  publish_event_recorded: "Ghi nhận xuất bản",
  performance_snapshot_imported: "Nhập ảnh chụp hiệu suất",
  performance_observation_recorded: "Ghi nhận quan sát hiệu suất",
  learning_candidate_created: "Tạo đề xuất học từ dữ liệu",
  learning_candidate_reviewed: "Duyệt đề xuất học từ dữ liệu",
  learning_application_applied: "Áp dụng đề xuất học từ dữ liệu",
  learning_validation_recorded: "Ghi nhận kiểm chứng học từ dữ liệu",
  learning_resolution_reviewed: "Duyệt kết quả kiểm chứng",
  learning_resolution_applied: "Áp dụng kết quả kiểm chứng",
};

const ENTITY_TYPE_VI: Record<string, string> = {
  signal: "Tín hiệu",
  need_hypothesis: "Giả thuyết nhu cầu",
  customer_insight: "Nhận định khách hàng",
  content_opportunity: "Cơ hội nội dung",
  content_item: "Nội dung",
  content_version: "Phiên bản nội dung",
  content_run: "Lượt sản xuất",
  publish_event: "Sự kiện xuất bản",
  performance_snapshot: "Ảnh chụp hiệu suất",
  content_performance_observation: "Quan sát hiệu suất nội dung",
  learning_candidate: "Đề xuất học từ dữ liệu",
  learning_application: "Lượt áp dụng học từ dữ liệu",
  learning_validation: "Lượt kiểm chứng học từ dữ liệu",
  learning_resolution: "Kết quả kiểm chứng học từ dữ liệu",
  learning_resolution_application: "Lượt áp dụng kết quả kiểm chứng",
};

const PUBLISH_ACTION_VI: Record<string, string> = {
  draft: "Tạo bản nháp",
  publish: "Xuất bản",
  update_draft: "Cập nhật bản nháp",
  update_publish: "Cập nhật bản đã xuất bản",
};

const EXTERNAL_STATUS_VI: Record<string, string> = {
  draft: "Bản nháp",
  publish: "Đã xuất bản",
  future: "Đã lên lịch",
  private: "Riêng tư",
};

const RUN_MODE_VI: Record<string, string> = {
  create: "tạo mới",
  update: "cập nhật",
  refresh: "làm mới",
  localize: "bản địa hóa",
  eval: "đánh giá",
  publish: "xuất bản",
};

const REF_PREFIX_VI: Record<string, string> = {
  selection: "Lựa chọn",
  selected_by: "Người chọn",
  case: "Hồ sơ",
  content_case: "Hồ sơ nội dung",
  content_item: "Nội dung",
  content_version: "Phiên bản nội dung",
  version: "Phiên bản",
  failure_code: "Mã lỗi",
  published_content: "Nội dung đã xuất bản",
  metric: "Chỉ số",
  target_type: "Loại đối tượng",
  target: "Đối tượng",
  review: "Lượt duyệt",
  learning_candidate: "Đề xuất học",
  learning_application: "Lượt áp dụng học",
  learning_validation: "Lượt kiểm chứng",
  resulting_target: "Đối tượng sau áp dụng",
};

export function digestEventKindLabel(value: string): string {
  return EVENT_KIND_VI[value] ?? value;
}

export function digestEntityTypeLabel(value: string): string {
  return ENTITY_TYPE_VI[value] ?? value;
}

export function digestStatusLabel(kind: string, status: string): string {
  if (kind === "content_opportunity_created") {
    const [decision, priority] = status.split(":", 2);
    return [uiDecisionLabel(decision), uiPriorityLabel(priority)]
      .filter(Boolean)
      .join(" · ");
  }

  if (kind === "content_opportunity_selected") {
    return uiDecisionLabel(status);
  }

  if (kind === "publish_event_recorded") {
    const [action, externalStatus] = status.split(":", 2);
    return [
      PUBLISH_ACTION_VI[action] ?? action,
      EXTERNAL_STATUS_VI[externalStatus] ?? externalStatus,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  if (kind === "learning_candidate_created") {
    return status
      .split(":")
      .map((value) => learningStatusLabel(value))
      .join(" · ");
  }

  if (kind === "learning_application_applied") {
    return learningTargetLabel(status);
  }

  if (kind.startsWith("learning_")) {
    return learningStatusLabel(status);
  }

  if (kind === "signal_captured") {
    return learningSourceKindLabel(status);
  }

  if (kind === "performance_observation_recorded") {
    return learningStatusLabel(status);
  }

  return uiStatusLabel(status);
}

export function digestSummaryLabel(kind: string, summary: string): string {
  if (kind === "learning_application_applied" || kind === "learning_resolution_applied") {
    return learningActionLabel(summary);
  }

  const started = /^Run mode (.+) started\.$/.exec(summary);
  if (kind === "content_run_started" && started) {
    return `Lượt sản xuất chế độ ${RUN_MODE_VI[started[1]] ?? started[1]} đã bắt đầu.`;
  }

  const completed = /^Run mode (.+) reached terminal state\.$/.exec(summary);
  if (kind === "content_run_completed" && completed) {
    return `Lượt sản xuất chế độ ${RUN_MODE_VI[completed[1]] ?? completed[1]} đã kết thúc.`;
  }

  const performanceWindow = /^(.+) window (.+) → (.+)$/.exec(summary);
  if (kind === "performance_snapshot_imported" && performanceWindow) {
    return `${performanceWindow[1]} · khoảng ${performanceWindow[2]} → ${performanceWindow[3]}`;
  }

  const validation = /^Validation v(\d+) for ([^;]+); human resolution remains separate\.$/.exec(summary);
  if (kind === "learning_validation_recorded" && validation) {
    return `Kiểm chứng v${validation[1]} cho ${learningTargetLabel(validation[2])}; kết quả duyệt của người dùng được xử lý riêng.`;
  }

  return summary;
}

export function digestRefLabel(ref: string): string {
  const separator = ref.indexOf(":");
  if (separator < 0) return ref;

  const prefix = ref.slice(0, separator);
  const rawValue = ref.slice(separator + 1);
  const label = REF_PREFIX_VI[prefix] ?? prefix;

  if (prefix === "selected_by") {
    const actor = rawValue.toLowerCase() === "founder" ? "Người sáng lập" : rawValue;
    return `${label} · ${actor}`;
  }

  if (prefix === "target_type") {
    return `${label} · ${learningTargetLabel(rawValue)}`;
  }

  return `${label} · ${rawValue}`;
}
