const DECISION_VI: Record<string, string> = {
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

const PRIORITY_VI: Record<string, string> = {
  NOW: "Ưu tiên ngay",
  NEXT: "Tiếp theo",
  LATER: "Để sau",
  HIGH: "Cao",
  MEDIUM: "Trung bình",
  LOW: "Thấp",
  NO: "Không ưu tiên",
};

const INTENT_VI: Record<string, string> = {
  learn: "Tìm hiểu",
  understand: "Hiểu rõ",
  compare: "So sánh",
  evaluate: "Đánh giá",
  trust: "Xây dựng niềm tin",
  plan_visit: "Lên kế hoạch ghé xem",
  consider_purchase: "Cân nhắc mua",
  post_purchase: "Sau khi mua",
  decide: "Ra quyết định",
  buy: "Mua",
  discover: "Khám phá",
  informational: "Tìm thông tin",
  transactional: "Thực hiện hành động",
  commercial: "Cân nhắc mua",
  navigational: "Tìm điểm đến",
};

export function uiDecisionLabel(value: string): string {
  return DECISION_VI[value] ?? value;
}

export function uiPriorityLabel(value: string): string {
  return PRIORITY_VI[value] ?? value;
}

export function uiIntentLabel(value: string): string {
  return INTENT_VI[value.toLowerCase()] ?? value;
}
