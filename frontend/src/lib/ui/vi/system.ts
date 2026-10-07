const SYSTEM_CHECK_VI: Record<string, string> = {
  database_binding: "Liên kết cơ sở dữ liệu",
  database: "Cơ sở dữ liệu",
  migration: "Phiên bản dữ liệu",
  test_database: "Cơ sở dữ liệu kiểm thử",
  codex_cli: "Codex CLI",
  antigravity_cli: "Antigravity",
  postgres_tools: "Công cụ PostgreSQL",
  journal_research_serper: "Tìm nguồn bằng Serper",
  journal_angle_settings: "Cấu hình góc tiếp cận",
  journal_angle_prompt: "Chỉ dẫn góc tiếp cận",
  journal_angle_recipe: "Công thức góc tiếp cận",
};

const SYSTEM_SCOPE_VI: Record<string, string> = {
  project: "Dự án",
  system: "Hệ thống",
  global: "Toàn cục",
};

const SYSTEM_ENVIRONMENT_VI: Record<string, string> = {
  development: "Phát triển",
  test: "Kiểm thử",
  testing: "Kiểm thử",
  staging: "Tiền sản xuất",
  production: "Sản xuất",
};

export function systemCheckLabel(value: string): string {
  return SYSTEM_CHECK_VI[value] ?? value;
}

export function systemScopeLabel(value: string): string {
  return SYSTEM_SCOPE_VI[value.toLowerCase()] ?? value;
}

export function systemEnvironmentLabel(value: string): string {
  return SYSTEM_ENVIRONMENT_VI[value.toLowerCase()] ?? value;
}
