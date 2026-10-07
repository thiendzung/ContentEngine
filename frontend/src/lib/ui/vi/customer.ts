const CUSTOMER_ORIGIN_VI: Record<string, string> = {
  founder_manual: "Người sáng lập nhập thủ công",
  research: "Nghiên cứu",
  learning: "Vòng học từ dữ liệu",
};

const CUSTOMER_RELATION_VI: Record<string, string> = {
  supports: "Ủng hộ",
  contradicts: "Mâu thuẫn",
  context: "Bối cảnh",
};

const NEED_TYPE_VI: Record<string, string> = {
  question: "Câu hỏi",
  problem: "Vấn đề",
  goal: "Mục tiêu",
  job: "Việc cần làm",
};

const CHANGE_KIND_VI: Record<string, string> = {
  NEW: "MỚI",
  SUPPORT: "ỦNG HỘ",
  CONTRADICT: "MÂU THUẪN",
  DUPLICATE: "TRÙNG",
};

const CUSTOMER_ENTITY_VI: Record<string, string> = {
  audience: "Nhóm khách hàng",
  audience_hypothesis: "Giả thuyết nhóm khách hàng",
  need: "Nhu cầu",
  need_hypothesis: "Giả thuyết nhu cầu",
  insight: "Nhận định khách hàng",
  customer_insight: "Nhận định khách hàng",
};

const INSIGHT_TYPE_VI: Record<string, string> = {
  job: "Việc cần làm",
  pain: "Nỗi đau",
  desire: "Mong muốn",
  question: "Câu hỏi",
  fear: "Lo ngại",
  objection: "Phản đối",
  barrier: "Rào cản",
  trigger: "Yếu tố kích hoạt",
  decision_factor: "Yếu tố quyết định",
  trust_builder: "Yếu tố tạo niềm tin",
  trust_breaker: "Yếu tố làm mất niềm tin",
  language: "Ngôn ngữ khách hàng",
  behaviour: "Hành vi",
  expectation: "Kỳ vọng",
  post_purchase_need: "Nhu cầu sau mua",
  referral_trigger: "Yếu tố thúc đẩy giới thiệu",
  repeat_purchase_trigger: "Yếu tố thúc đẩy mua lại",
};

const JOURNEY_STAGE_VI: Record<string, string> = {
  unaware: "Chưa nhận biết",
  aware: "Đã nhận biết",
  interested: "Quan tâm",
  preference: "Hình thành ưu tiên",
  trust: "Xây dựng niềm tin",
  purchase: "Mua hàng",
  satisfied: "Hài lòng",
  referral: "Giới thiệu",
  repeat_purchase: "Mua lại",
};

export function customerOriginLabel(value: string): string {
  return CUSTOMER_ORIGIN_VI[value] ?? value;
}

export function customerRelationLabel(value: string): string {
  return CUSTOMER_RELATION_VI[value] ?? value;
}

export function customerNeedTypeLabel(value: string): string {
  return NEED_TYPE_VI[value.toLowerCase()] ?? value;
}

export function customerChangeKindLabel(value: string): string {
  return CHANGE_KIND_VI[value] ?? value;
}

export function customerEntityTypeLabel(value: string): string {
  return CUSTOMER_ENTITY_VI[value.toLowerCase()] ?? value;
}

export function customerInsightTypeLabel(value: string): string {
  return INSIGHT_TYPE_VI[value.toLowerCase()] ?? value;
}

export function customerJourneyStageLabel(key: string, fallbackLabel: string): string {
  return JOURNEY_STAGE_VI[key.toLowerCase()] ?? fallbackLabel;
}
