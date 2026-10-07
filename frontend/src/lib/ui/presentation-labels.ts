export function uiStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    READY: "Sẵn sàng",
    BLOCKED: "Bị chặn",
    OPTIONAL: "Không bắt buộc",
    RUNNING: "Đang chạy",
    QUEUED: "Đang chờ",
    COMPLETED: "Hoàn thành",
    COMPLETE: "Hoàn thành",
    FAILED: "Thất bại",
    PASS: "Đạt",
    WARN: "Cảnh báo",
    FAIL: "Không đạt",
    PENDING: "Đang chờ",
    ACTIVE: "Đang hoạt động",
    INACTIVE: "Không hoạt động",
    PROPOSED: "Đề xuất",
    CANDIDATE: "Ứng viên",
    TESTING: "Đang kiểm chứng",
    SUPPORTED: "Đã có bằng chứng hỗ trợ",
    REJECTED: "Đã bác bỏ",
    INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
    READY_FOR_REVIEW: "Sẵn sàng để duyệt",
    REQUEST_MORE_EVIDENCE: "Cần thêm bằng chứng",
    NEEDS_MORE_EVIDENCE: "Cần thêm bằng chứng",
    INCONCLUSIVE: "Chưa đủ kết luận",
    VALIDATED: "Đã kiểm chứng",
    REGRESSED: "Thoái lui",
    CONTESTED: "Có tranh luận",
    APPROVE: "Duyệt",
    PROMOTE: "Đưa vào áp dụng",
    KEEP: "Giữ nguyên",
    REJECT: "Bác bỏ",
    ROLLBACK: "Hoàn tác",
    ARCHIVE_CANDIDATE: "Lưu trữ ứng viên",
    CONSISTENT: "Nhất quán",
    INCONSISTENT: "Không nhất quán",
    PUBLISHED: "Đã xuất bản",
    NOT_PUBLISHED: "Chưa xuất bản",
    APPROVED_NOT_PUBLISHED: "Đã duyệt · chưa xuất bản",
    AWAITING_APPROVAL: "Chờ duyệt",
    WAITING_APPROVAL: "Chờ duyệt",
    AWAITING_FOUNDER_APPROVAL: "Chờ Người sáng lập duyệt",
    RECONCILIATION_REQUIRED: "Cần xác nhận hợp nhất",
    ADMITTED: "Có thể tiếp tục",
    MISSING: "Đang thiếu",
    PLANNED: "Đã lên kế hoạch",
    IN_PROGRESS: "Đang sản xuất",
    NEEDS_UPDATE: "Cần cập nhật",
    WEAK: "Nội dung yếu",
    ANSWERED: "Đã trả lời",
    PARTIAL: "Đã có một phần",
    STALE: "Đã cũ",
    COLLISION: "Có xung đột",
    MIXED: "Hỗn hợp",
    ok: "Bình thường",
    completed: "Hoàn thành",
    failed: "Thất bại",
    running: "Đang chạy",
    queued: "Đang chờ",
  };
  return labels[value] ?? value;
}

export function uiDecisionLabel(value: string): string {
  const labels: Record<string, string> = {
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
  return labels[value] ?? value;
}

export function uiPriorityLabel(value: string): string {
  const labels: Record<string, string> = {
    NOW: "Ưu tiên ngay",
    NEXT: "Tiếp theo",
    LATER: "Để sau",
    HIGH: "Cao",
    MEDIUM: "Trung bình",
    LOW: "Thấp",
  };
  return labels[value] ?? value;
}

export function uiIntentLabel(value: string): string {
  const labels: Record<string, string> = {
    learn: "Tìm hiểu",
    evaluate: "Đánh giá",
    compare: "So sánh",
    decide: "Ra quyết định",
    buy: "Mua",
    discover: "Khám phá",
    informational: "Tìm thông tin",
    transactional: "Thực hiện hành động",
    commercial: "Cân nhắc mua",
    navigational: "Tìm điểm đến",
  };
  return labels[value.toLowerCase()] ?? value;
}

export function uiDomainLabel(value: string): string {
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

export function uiBooleanLabel(value: boolean): string {
  return value ? "Có" : "Không";
}
