const DOMAIN_VI: Record<string, string> = {
  customer: "Khách hàng",
  content: "Nội dung",
  production: "Sản xuất",
  publication: "Xuất bản",
  measurement: "Đo lường",
  learning: "Học từ dữ liệu",
};

export function uiDomainLabel(value: string): string {
  return DOMAIN_VI[value] ?? value;
}
