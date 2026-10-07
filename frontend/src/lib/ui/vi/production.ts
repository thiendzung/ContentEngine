const PRODUCTION_GROUP_VI: Record<string, string> = {
  RUNNING: "Đang thực hiện",
  QUEUED: "Chờ xử lý",
  BLOCKED: "Bị chặn",
  AWAITING_APPROVAL: "Chờ duyệt",
  COMPLETED: "Hoàn thành",
};

const PRODUCTION_STAGE_VI: Record<string, string> = {
  intake: "Tiếp nhận",
  start_to_angle: "Nghiên cứu & tạo góc tiếp cận",
  angle: "Chọn góc tiếp cận",
  angle_generation: "Tạo góc tiếp cận",
  outline: "Lập dàn ý",
  journal_outline: "Lập dàn ý",
  writer: "Viết nội dung",
  journal_writer_vi: "Viết tiếng Việt",
  journal_writer_en: "Viết tiếng Anh",
  review_revise: "Rà soát & chỉnh sửa",
  assertion_audit: "Kiểm tra khẳng định",
  source_copy_check: "Kiểm tra trùng nguồn",
  source_copy: "Kiểm tra trùng nguồn",
  quality_gate: "Kiểm tra chất lượng",
  final_review: "Duyệt nội dung cuối",
  revision_requested: "Chờ chỉnh sửa",
  rejected: "Đã từ chối",
  approved: "Đã duyệt",
  published: "Đã xuất bản",
  data_conflict: "Xử lý dữ liệu không nhất quán",
};

const PRODUCTION_ACTION_VI: Record<string, string> = {
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

export function productionGroupLabel(value: string): string {
  return PRODUCTION_GROUP_VI[value] ?? "Khác";
}

export function productionStageLabel(value: string): string {
  const normalized = value.toLowerCase();
  if (PRODUCTION_STAGE_VI[normalized]) return PRODUCTION_STAGE_VI[normalized];

  if (normalized.includes("angle")) return "Tạo góc tiếp cận";
  if (normalized.includes("outline")) return "Lập dàn ý";
  if (normalized.includes("review_revise")) {
    if (normalized.includes("_vi")) return "Rà soát tiếng Việt";
    if (normalized.includes("_en")) return "Rà soát tiếng Anh";
    return "Rà soát & chỉnh sửa";
  }
  if (normalized.includes("writer")) {
    if (normalized.includes("_vi")) return "Viết tiếng Việt";
    if (normalized.includes("_en")) return "Viết tiếng Anh";
    return "Viết nội dung";
  }
  if (normalized.includes("assertion") || normalized.includes("audit")) {
    return "Kiểm tra khẳng định";
  }
  if (normalized.includes("source_copy") || normalized.includes("source-copy")) {
    return "Kiểm tra trùng nguồn";
  }
  if (normalized.includes("cleanup")) return "Dọn lỗi sau kiểm tra";
  if (normalized.includes("package")) return "Đóng gói vận hành";
  if (normalized.includes("approval") || normalized.includes("final_review")) {
    return "Duyệt nội dung cuối";
  }
  return "Tác vụ nội dung";
}

export function productionActionLabel(value: string): string {
  return PRODUCTION_ACTION_VI[value] ?? "Theo dõi trạng thái hiện tại";
}
