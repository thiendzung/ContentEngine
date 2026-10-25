import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

function requireText(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`UX static check failed: ${label} missing ${JSON.stringify(needle)}`);
  }
}

const fixtures = read("src/lib/operator/ux-fixtures.ts");
const fixturePage = read("src/app/operator/ux-fixtures/[state]/page.tsx");
const workspace = read("src/components/operator/operator-case-workspace.tsx");
const historyPanel = read("src/components/operator/operator-case-history.tsx");
const journalApi = read("src/lib/operator/journal-api.ts");
const historyProjection = read("../backend/app/modules/content_engine/journal/operator_history.py");
const css = read("src/app/operator/operator.css");
const plan = read("../docs/releases/UX_SIMPLE_OPERATOR_V1_PLAN.md");

for (const state of [
  "ready",
  "queued",
  "running",
  "blocked",
  "approval",
  "complete",
  "error",
  "stale",
  "empty",
]) {
  requireText(fixtures, `"${state}"`, `fixture state ${state}`);
  requireText(fixturePage, `"${state}"`, `fixture route state ${state}`);
}

requireText(
  fixturePage,
  'process.env.NEXT_PUBLIC_UX_FIXTURES !== "1"',
  "production fixture gate",
);
requireText(workspace, 'window.addEventListener("focus"', "focus refresh");
requireText(
  workspace,
  'document.addEventListener("visibilitychange"',
  "visibility refresh",
);
requireText(
  workspace,
  "setReconcileRequired(uxInitialReconcileRequired);",
  "stale fixture survives initial load",
);
requireText(
  workspace,
  "setReconcileRequired(false);",
  "successful reconciliation clears stale state",
);
if (workspace.includes("setInterval(")) {
  throw new Error("UX static check failed: interval polling reintroduced");
}
requireText(css, "@media (max-width: 680px)", "narrow breakpoint");
requireText(css, ".operator-progress-strip", "progress strip");
requireText(css, "grid-template-columns: 1fr;", "single-column reflow");
requireText(plan, "UX_UI_READY", "separate UX gate");
requireText(plan, "BACKEND_INTEGRATION_READY", "separate integration gate");
requireText(plan, "1440/1024/390/320 px", "320px reflow proof");
requireText(fixtures, "getOperatorUxHistoryFixture", "history fixture");
requireText(journalApi, "loadOperatorCaseHistory", "history API client");
requireText(historyPanel, "Nhật ký bài viết", "readable history panel");
requireText(historyPanel, "Tải JSON", "safe JSON export");
requireText(historyPanel, "Tải Markdown", "safe Markdown export");
requireText(workspace, "<OperatorCaseHistoryPanel", "history mounted in workspace");
requireText(workspace, "BlockedCaseExplainability", "blocked case explainability");
requireText(workspace, "Bằng chứng đã có nhưng chưa đủ độ sâu", "insufficient support copy");
requireText(workspace, "Thử lại sau khi đã xử lý", "guarded retry label");
requireText(fixtures, 'blocker_code: "insufficient_support"', "real blocked evidence fixture");
requireText(css, ".operator-blocked-explainability", "blocked explainability styling");
requireText(css, ".operator-coverage-review", "coverage review styling");

for (const forbidden of [
  "failure_message",
  "runtime_metadata_json",
  "result_ref",
  ".content_json",
  "approval.comment",
  "actor_id",
  "request_fingerprint",
]) {
  if (historyProjection.includes(forbidden)) {
    throw new Error(
      `UX static check failed: sanitized history references forbidden field ${forbidden}`,
    );
  }
}

console.log("PASS_UX_SIMPLE_STATIC_FIXTURE_GATE");
