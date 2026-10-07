const STATUS_LABELS: Record<string, string> = {
  PROPOSED: "Đề xuất",
  CANDIDATE: "Ứng viên",
  TESTING: "Đang kiểm chứng",
  SUPPORTED: "Có bằng chứng hỗ trợ",
  REJECTED: "Đã bác bỏ",
  INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
  ACTIVE: "Đang hoạt động",
  INACTIVE: "Không hoạt động",
  RETIRED: "Đã ngừng",
  READY: "Sẵn sàng",
  NOT_READY: "Chưa sẵn sàng",
  OPTIONAL: "Không bắt buộc",
  BLOCKED: "Bị chặn",
  QUEUED: "Đang chờ xử lý",
  RUNNING: "Đang thực hiện",
  COMPLETE: "Hoàn thành",
  COMPLETED: "Hoàn thành",
  FAILED: "Thất bại",
  PENDING: "Đang chờ",
  AWAITING_APPROVAL: "Chờ duyệt",
  WAITING_APPROVAL: "Chờ duyệt",
  READY_FOR_REVIEW: "Sẵn sàng duyệt",
  VALIDATED: "Đã xác minh",
  REGRESSED: "Suy giảm",
  CONTESTED: "Có tranh luận",
  APPROVE: "Chấp thuận",
  REJECT: "Bác bỏ",
  PROMOTE: "Nâng thành quy tắc",
  KEEP: "Giữ nguyên",
  ROLLBACK: "Hoàn tác",
  ARCHIVE_CANDIDATE: "Lưu trữ đề xuất",
  REQUEST_MORE_EVIDENCE: "Yêu cầu thêm bằng chứng",
  NEEDS_MORE_EVIDENCE: "Cần thêm bằng chứng",
  INCONCLUSIVE: "Chưa thể kết luận",
  ANSWERED: "Đã trả lời",
  PARTIAL: "Đã có một phần",
  MISSING: "Đang thiếu",
  STALE: "Cần làm mới",
  COLLISION: "Có xung đột",
  MIXED: "Hỗn hợp",
  PUBLISHED: "Đã xuất bản",
  WORKING: "Đang vận hành",
  DRAFT: "Bản nháp",
  CONSISTENT: "Nhất quán",
  INCONSISTENT_STATE: "Trạng thái không nhất quán",
  REVIEW_REQUIRED: "Cần duyệt",
  QUALITY_BLOCKED: "Bị chặn bởi chất lượng",
  ADMITTED: "Được phép tiếp tục",
  RECONCILIATION_REQUIRED: "Cần xác nhận hợp nhất",
  BLOCKED_ROUTE_STALE: "Bị chặn: hướng xử lý đã cũ",
  BLOCKED_SELECTION_STALE: "Bị chặn: lựa chọn đã cũ",
  BLOCKED_OPPORTUNITY_STALE: "Bị chặn: cơ hội nội dung đã cũ",
  BLOCKED_TARGET_STALE: "Bị chặn: nội dung đích đã thay đổi",
  ok: "Tốt",
  ready: "Sẵn sàng",
  optional: "Không bắt buộc",
  blocked: "Bị chặn",
  queued: "Đang chờ xử lý",
  running: "Đang thực hiện",
  completed: "Hoàn thành",
  failed: "Thất bại",
  pending: "Đang chờ",
  draft: "Bản nháp",
  active: "Đang hoạt động",
  inactive: "Không hoạt động",
  published: "Đã xuất bản",
  rejected: "Đã từ chối",
  approved: "Đã duyệt",
  not_published: "Chưa xuất bản",
};

const DECISION_LABELS: Record<string, string> = {
  CREATE: "Tạo mới",
  UPDATE: "Cập nhật",
  REFRESH: "Làm mới",
  MERGE: "Hợp nhất",
  LINK_ONLY: "Chỉ liên kết",
  DO_NOT_WRITE: "Không viết",
  CREATE_NEW_CONTENT: "Tạo nội dung mới",
  REVISE_EXISTING_CONTENT: "Tạo bản cập nhật",
  REFRESH_EXISTING_CONTENT: "Làm mới nội dung hiện có",
  RECONCILE_CONTENT: "Hợp nhất nội dung xung đột",
  NO_PRODUCTION: "Không đưa vào sản xuất",
  STOP: "Dừng",
};

const PRIORITY_LABELS: Record<string, string> = {
  NOW: "Làm ngay",
  NEXT: "Làm tiếp",
  LATER: "Để sau",
  HIGH: "Cao",
  MEDIUM: "Trung bình",
  LOW: "Thấp",
};

const DOMAIN_LABELS: Record<string, string> = {
  customer: "Khách hàng",
  content: "Nội dung",
  production: "Sản xuất",
  publication: "Xuất bản",
  measurement: "Đo lường",
  learning: "Học từ dữ liệu",
};

const ROLE_LABELS: Record<string, string> = {
  pillar: "Nội dung trụ cột",
  cluster: "Cụm nội dung",
};

const RELATION_LABELS: Record<string, string> = {
  supports: "Ủng hộ",
  contradicts: "Mâu thuẫn",
  context: "Bối cảnh",
};

const INTENT_LABELS: Record<string, string> = {
  learn: "Tìm hiểu",
  inform: "Tìm thông tin",
  discover: "Khám phá",
  evaluate: "Đánh giá",
  compare: "So sánh",
  consider: "Cân nhắc",
  buy: "Mua",
  purchase: "Mua",
  transactional: "Giao dịch",
  informational: "Thông tin",
  navigational: "Điều hướng",
  commercial: "Thương mại",
};

const LEARNING_ACTION_LABELS: Record<string, string> = {
  APPROVE: "Chấp thuận",
  REJECT: "Bác bỏ",
  PROMOTE: "Nâng thành quy tắc",
  KEEP: "Giữ nguyên",
  ROLLBACK: "Hoàn tác",
  ARCHIVE_CANDIDATE: "Lưu trữ đề xuất",
  REQUEST_MORE_EVIDENCE: "Yêu cầu thêm bằng chứng",
  NEEDS_MORE_EVIDENCE: "Cần thêm bằng chứng",
  INCONCLUSIVE: "Chưa thể kết luận",
};

const TARGET_TYPE_LABELS: Record<string, string> = {
  audience: "Nhóm khách hàng",
  need: "Nhu cầu",
  insight: "Hiểu biết khách hàng",
  customer_insight: "Hiểu biết khách hàng",
  content: "Nội dung",
  content_item: "Nội dung",
  content_opportunity: "Cơ hội nội dung",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  SEARCH: "Tìm kiếm",
  research: "Nghiên cứu",
  founder_manual: "Người sáng lập nhập thủ công",
  learning: "Học từ dữ liệu",
  measurement: "Đo lường",
  fixture: "Dữ liệu kiểm thử",
};

export function uiStatusLabel(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "Chưa có";
  return STATUS_LABELS[value] ?? STATUS_LABELS[value.toUpperCase()] ?? value;
}

export function uiDecisionLabel(value: string | null | undefined): string {
  if (!value) return "Chưa có";
  return DECISION_LABELS[value] ?? value;
}

export function uiPriorityLabel(value: string | null | undefined): string {
  if (!value) return "Chưa có";
  return PRIORITY_LABELS[value] ?? value;
}

export function uiDomainLabel(value: string): string {
  return DOMAIN_LABELS[value] ?? value;
}

export function uiContentRoleLabel(value: string | null | undefined): string {
  if (!value) return "Chưa xác định";
  return ROLE_LABELS[value.toLowerCase()] ?? value;
}

export function uiRelationLabel(value: string | null | undefined): string {
  if (!value) return "Chưa xác định";
  return RELATION_LABELS[value.toLowerCase()] ?? value;
}

export function uiIntentLabel(value: string | null | undefined): string {
  if (!value) return "Chưa xác định";
  return INTENT_LABELS[value.toLowerCase()] ?? value;
}

export function uiLearningActionLabel(value: string | null | undefined): string {
  if (!value) return "Chưa có";
  return LEARNING_ACTION_LABELS[value] ?? value;
}

export function uiTargetTypeLabel(value: string | null | undefined): string {
  if (!value) return "Chưa xác định";
  return TARGET_TYPE_LABELS[value.toLowerCase()] ?? value;
}

export function uiSourceKindLabel(value: string | null | undefined): string {
  if (!value) return "Chưa xác định";
  return SOURCE_KIND_LABELS[value] ?? SOURCE_KIND_LABELS[value.toLowerCase()] ?? value;
}

export function uiBooleanLabel(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "Chưa xác định";
  return value ? "Có" : "Không";
}
