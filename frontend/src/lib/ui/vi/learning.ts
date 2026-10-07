import { uiStatusLabel } from "./status";

const LEARNING_STATUS_VI: Record<string, string> = {
  NEEDS_EVIDENCE: "Cần thêm bằng chứng",
  EARLY_SIGNAL: "Tín hiệu ban đầu",
  REPEATED_PATTERN: "Mẫu lặp lại",
  READY_FOR_REVIEW: "Sẵn sàng để duyệt",
  CONTESTED: "Có tranh luận",
  OPEN: "Đang mở",
  SUPERSEDED: "Đã được thay thế",
  ARCHIVED: "Đã lưu trữ",
  NO_MAP_CHANGE: "Không thay đổi Bản đồ khách hàng",
};

const LEARNING_TARGET_VI: Record<string, string> = {
  customer_insight: "Nhận định khách hàng",
  need_hypothesis: "Giả thuyết nhu cầu",
  new_customer_insight: "Nhận định khách hàng mới",
  no_map_change: "Không thay đổi Bản đồ khách hàng",
};

const LEARNING_RELATION_VI: Record<string, string> = {
  supports: "Ủng hộ",
  contradicts: "Mâu thuẫn",
  context: "Bối cảnh",
  proposes: "Đề xuất",
  no_change: "Không thay đổi",
};

const LEARNING_EVIDENCE_KIND_VI: Record<string, string> = {
  signal: "Tín hiệu thực tế",
  measurement_observation: "Quan sát đo lường",
  assessment_artifact: "Tài liệu đánh giá",
};

const LEARNING_SOURCE_KIND_VI: Record<string, string> = {
  MARKET: "Thị trường",
  SEARCH: "Tìm kiếm",
  MOTGU: "MOTGU",
};

const LEARNING_ACTION_VI: Record<string, string> = {
  link_need_signals: "Liên kết tín hiệu với nhu cầu",
  link_insight_signals: "Liên kết tín hiệu với nhận định",
  create_candidate_insight: "Tạo nhận định khách hàng ứng viên",
  no_map_change: "Không thay đổi Bản đồ khách hàng",
  review_need: "Cập nhật trạng thái nhu cầu sau duyệt",
  review_insight: "Cập nhật trạng thái nhận định sau duyệt",
  archive_candidate: "Lưu trữ đề xuất học",
};

export function learningStatusLabel(value: string): string {
  return LEARNING_STATUS_VI[value] ?? uiStatusLabel(value);
}

export function learningTargetLabel(value: string): string {
  return LEARNING_TARGET_VI[value] ?? value;
}

export function learningRelationLabel(value: string): string {
  return LEARNING_RELATION_VI[value] ?? value;
}

export function learningEvidenceKindLabel(value: string): string {
  return LEARNING_EVIDENCE_KIND_VI[value] ?? value;
}

export function learningSourceKindLabel(value: string): string {
  return LEARNING_SOURCE_KIND_VI[value] ?? value;
}

export function learningActionLabel(value: string): string {
  return LEARNING_ACTION_VI[value] ?? value;
}
