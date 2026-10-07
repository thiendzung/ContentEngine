export function founderStatusLabel(value: string | null | undefined): string {
  if (!value) return "—";

  const labels: Record<string, string> = {
    READY: "Sẵn sàng",
    READY_FOR_REVIEW: "Sẵn sàng để duyệt",
    READY_FOR_HUMAN_SELECTION: "Sẵn sàng để chọn",
    NOT_READY: "Chưa sẵn sàng",
    PENDING: "Đang chờ",
    QUEUED: "Đang chờ xử lý",
    RUNNING: "Đang thực hiện",
    ACTIVE: "Đang hoạt động",
    BLOCKED: "Bị chặn",
    COMPLETED: "Hoàn thành",
    COMPLETE: "Hoàn thành",
    FAILED: "Thất bại",
    ERROR: "Có lỗi",
    PASS: "Đạt",
    WARN: "Cảnh báo",
    FAIL: "Không đạt",
    HEALTHY: "Bình thường",
    UNHEALTHY: "Có vấn đề",
    OPTIONAL: "Không bắt buộc",
    AWAITING_APPROVAL: "Chờ duyệt",
    WAITING_APPROVAL: "Chờ duyệt",
    AWAITING_FOUNDER_APPROVAL: "Chờ duyệt cuối",
    APPROVED: "Đã duyệt",
    REJECTED: "Đã bác bỏ",
    REVISION_REQUESTED: "Đã yêu cầu sửa",
    VALIDATED: "Đã kiểm chứng",
    REGRESSED: "Bị suy giảm",
    CONTESTED: "Có tranh luận",
    RESOLVED: "Đã xử lý",
    PROPOSED: "Đề xuất",
    CANDIDATE: "Ứng viên",
    TESTING: "Đang kiểm chứng",
    SUPPORTED: "Đã có hỗ trợ",
    INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
    INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
    CONSISTENT: "Nhất quán",
    INCONSISTENT: "Không nhất quán",
    INCONSISTENT_STATE: "Trạng thái không nhất quán",
    NOT_PUBLISHED: "Chưa xuất bản",
    PUBLISHED: "Đã xuất bản",
    APPROVED_NOT_PUBLISHED: "Đã duyệt, chưa xuất bản",
    QUALITY_BLOCKED: "Bị chặn bởi chất lượng",
    CREATE: "Tạo mới",
    UPDATE: "Cập nhật",
    REFRESH: "Làm mới",
    MERGE: "Hợp nhất",
    LINK_ONLY: "Chỉ liên kết",
    DO_NOT_WRITE: "Không viết",
    NEXT: "Ưu tiên tiếp theo",
    LATER: "Để sau",
    HIGH: "Cao",
    MEDIUM: "Trung bình",
    LOW: "Thấp",
    NEW: "Mới",
    SUPPORT: "Ủng hộ",
    CONTRADICT: "Mâu thuẫn",
    DUPLICATE: "Trùng lặp",
    PROMOTE: "Nâng cấp",
    KEEP: "Giữ nguyên",
    ROLLBACK: "Hoàn tác",
    ARCHIVE_CANDIDATE: "Lưu trữ ứng viên",
    RECONCILIATION_REQUIRED: "Cần xác nhận hợp nhất",
    ADMITTED: "Được phép tiếp tục",
  };

  return labels[value] ?? value;
}

export function founderLocaleLabel(value: string): string {
  if (value === "vi-VN") return "Tiếng Việt";
  if (value === "en") return "Tiếng Anh";
  return value;
}

export function founderDomainLabel(value: string): string {
  const labels: Record<string, string> = {
    customer: "Khách hàng",
    content: "Nội dung",
    production: "Sản xuất",
    publication: "Xuất bản",
    measurement: "Đo lường",
    learning: "Học từ dữ liệu",
  };
  return labels[value] ?? value;
}

export function founderBooleanLabel(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "Chưa xác định";
  return value ? "Có" : "Không";
}

export function founderDecisionLabel(value: string): string {
  const labels: Record<string, string> = {
    APPROVE: "Duyệt",
    REJECT: "Bác bỏ",
    PROMOTE: "Nâng cấp",
    KEEP: "Giữ nguyên",
    ROLLBACK: "Hoàn tác",
    ARCHIVE_CANDIDATE: "Lưu trữ ứng viên",
    CREATE: "Tạo mới",
    UPDATE: "Cập nhật",
    REFRESH: "Làm mới",
    MERGE: "Hợp nhất",
    LINK_ONLY: "Chỉ liên kết",
    DO_NOT_WRITE: "Không viết",
  };
  return labels[value] ?? founderStatusLabel(value);
}

export function founderPriorityLabel(value: string): string {
  const labels: Record<string, string> = {
    NEXT: "Ưu tiên tiếp theo",
    LATER: "Để sau",
    HIGH: "Cao",
    MEDIUM: "Trung bình",
    LOW: "Thấp",
  };
  return labels[value] ?? value;
}

export function founderIntentLabel(value: string): string {
  const labels: Record<string, string> = {
    learn: "Tìm hiểu",
    discover: "Khám phá",
    evaluate: "Đánh giá",
    compare: "So sánh",
    decide: "Ra quyết định",
    buy: "Mua",
    maintain: "Duy trì",
    refresh: "Cập nhật",
  };
  return labels[value.toLowerCase()] ?? value;
}

export function founderContentRoleLabel(value: string): string {
  const labels: Record<string, string> = {
    pillar: "Nội dung trụ cột",
    cluster: "Nội dung cụm",
    supporting: "Nội dung hỗ trợ",
    journal: "Bài chuyên sâu",
  };
  return labels[value.toLowerCase()] ?? value;
}

export function founderRelationLabel(value: string): string {
  const labels: Record<string, string> = {
    supports: "Ủng hộ",
    contradicts: "Mâu thuẫn",
    context: "Bối cảnh",
  };
  return labels[value] ?? value;
}
