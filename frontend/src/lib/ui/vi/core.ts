export function needsMeTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    content_approval: "Duyệt nội dung",
    publish_authorization: "Cho phép xuất bản",
    policy_gate: "Cổng chính sách",
    learning_candidate_review: "Duyệt đề xuất học từ dữ liệu",
    learning_resolution: "Xử lý kết quả kiểm chứng học từ dữ liệu",
  };
  return labels[value] ?? value;
}
