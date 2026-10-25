"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  loadOperatorCaseHistory,
  type OperatorCaseHistory,
  type OperatorHistoryEvent,
} from "../../lib/operator/journal-api";
import {
  operatorPhaseLabel,
  operatorQualityResultLabel,
  operatorQualityStageLabel,
} from "../../lib/operator/operator-labels";

const RECENT_COUNT = 5;

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("vi-VN", {
        dateStyle: "short",
        timeStyle: "medium",
      });
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    created: "Đã tạo",
    accepted: "Đã nhận",
    queued: "Đang chờ",
    pending: "Đang chờ",
    running: "Đang xử lý",
    leased: "Đang xử lý",
    called: "Đã gọi",
    skipped: "Bỏ qua",
    stopped: "Đã dừng",
    waiting_approval: "Chờ duyệt",
    completed: "Hoàn thành",
    approved: "Đã duyệt",
    changes_requested: "Yêu cầu sửa",
    rejected: "Đã từ chối",
    failed: "Có lỗi",
    cancelled: "Đã hủy",
    pass: "Đạt",
    warn: "Cảnh báo",
    fail: "Không đạt",
  };
  return labels[value] ?? value;
}

function intentLabel(value: string) {
  const labels: Record<string, string> = {
    create: "Tạo bài",
    start: "Bắt đầu",
    continue: "Tiếp tục",
    resume: "Tiếp tục lại",
    retry: "Thử lại",
    cancel: "Hủy",
    approve: "Duyệt",
    request_changes: "Yêu cầu sửa",
    reject: "Từ chối",
  };
  return labels[value] ?? value;
}

function researchReasonLabel(value: string | null | undefined) {
  if (!value) return null;
  const labels: Record<string, string> = {
    default_google_discovery: "Tìm nguồn ban đầu",
    evidence_candidate_authority_recovery: "Tìm nguồn có thẩm quyền",
    evidence_candidate_exa_unavailable_use_tavily_once:
      "Exa không sẵn sàng; dùng Tavily một lần",
    evidence_candidate_exa_insufficient_use_tavily_once:
      "Nguồn từ Exa chưa đủ; dùng Tavily một lần",
    evidence_candidate_fallbacks_exhausted:
      "Đã dùng hết lượt tìm nguồn có thẩm quyền",
    internal_knowledge_sufficient: "Nguồn nội bộ đã đủ",
    insufficient_for_request_external_search_required:
      "Nguồn nội bộ chưa đủ; cần tìm bên ngoài",
    serper_sufficient: "Nguồn từ Serper đã đủ để đọc",
    exa_sufficient: "Nguồn từ Exa đã đủ để đọc",
    tavily_sufficient: "Nguồn từ Tavily đã đủ để đọc",
    jina_candidates_exhausted: "Không đọc được đủ trang đã chọn",
    research_exception: "Nghiên cứu dừng vì lỗi kỹ thuật",
  };
  return labels[value] ?? value;
}

function approvalLabel(stage: string, decision: string | null) {
  const scope = stage === "angle"
    ? "góc tiếp cận"
    : stage === "outline"
      ? "dàn ý"
      : stage === "final_review"
        ? "bản cuối"
        : operatorPhaseLabel(stage).toLowerCase();
  if (decision === "changes_requested") return `Yêu cầu sửa ${scope}`;
  if (decision === "rejected") return `Từ chối ${scope}`;
  return `Duyệt ${scope}`;
}

function eventTitle(event: OperatorHistoryEvent) {
  if (event.kind === "command") return intentLabel(event.stage);
  if (event.kind === "research") {
    return event.stage === "research_summary"
      ? "Nghiên cứu nguồn"
      : `Nguồn nghiên cứu · ${event.provider ?? "không xác định"}`;
  }
  if (event.kind === "approval") return approvalLabel(event.stage, event.decision);
  if (event.kind === "quality") {
    return operatorQualityStageLabel(event.evaluator_key ?? event.stage);
  }
  if (event.kind === "model") return "AI xử lý · " + operatorPhaseLabel(event.stage);
  if (event.kind === "tool") return "Công cụ · " + event.stage;
  if (event.kind === "artifact") return "Tạo đầu ra · " + event.stage;
  if (event.kind === "step") return operatorPhaseLabel(event.stage);
  return "Lượt sản xuất · " + operatorPhaseLabel(event.stage);
}

function eventSummary(event: OperatorHistoryEvent) {
  if (event.kind === "research") {
    const reason = researchReasonLabel(event.reason_code);
    if (event.stage === "research_summary") {
      const calls = event.provider_call_count;
      const pages = event.pages_read;
      const counts = [
        typeof calls === "number" ? `${calls} lượt provider` : null,
        typeof pages === "number" ? `${pages} trang đã đọc` : null,
      ].filter(Boolean).join(" · ");
      return [counts, reason].filter(Boolean).join(" · ")
        || "Đã lưu chẩn đoán nghiên cứu an toàn.";
    }
    if (event.status === "called") {
      return reason ? `Đã gọi provider: ${reason}.` : "Provider đã được gọi.";
    }
    if (event.status === "skipped") {
      return reason ? `Không cần gọi: ${reason}.` : "Provider được bỏ qua theo policy.";
    }
    if (event.status === "failed") {
      return reason
        ? `Provider không trả kết quả dùng được: ${reason}.`
        : "Provider không trả kết quả dùng được.";
    }
    return reason ?? "Provider dừng theo giới hạn nghiên cứu.";
  }
  if (event.error_code) {
    return "Bước này có vấn đề và đã lưu mã chẩn đoán an toàn.";
  }
  if (event.kind === "quality") {
    return `Kết quả kiểm tra: ${operatorQualityResultLabel(event.result ?? event.status)}.`;
  }
  if (event.kind === "approval") {
    return event.decision === "changes_requested"
      ? "Người duyệt yêu cầu chỉnh sửa trước khi tiếp tục."
      : event.decision === "rejected"
        ? "Người duyệt đã từ chối phiên bản này."
        : "Quyết định duyệt đã được ghi nhận.";
  }
  if (event.kind === "model" || event.kind === "tool") {
    return event.latency_ms !== null
      ? `Hoàn tất trong khoảng ${Math.max(1, Math.round(event.latency_ms / 1000))} giây.`
      : "Thông tin kỹ thuật được lưu trong nhật ký.";
  }
  if (event.status === "waiting_approval") {
    return "Hệ thống dừng để chờ quyết định của người duyệt.";
  }
  if (event.status === "running") return "Hệ thống đang xử lý bước này.";
  if (event.status === "queued" || event.status === "pending") return "Bước đang chờ được xử lý.";
  if (event.status === "completed" || event.status === "created") return "Bước đã hoàn thành.";
  return "Trạng thái đã được ghi vào nhật ký.";
}

function eventClass(event: OperatorHistoryEvent) {
  if (["failed", "rejected", "fail"].includes(event.status)) return "problem";
  if (event.status === "warn") return "warning";
  if (["running", "queued", "pending", "waiting_approval"].includes(event.status)) return "active";
  return "complete";
}

function downloadFile(filename: string, contents: string, type: string) {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function supportMarkdown(history: OperatorCaseHistory) {
  const lines = [
    "# ContentEngine support report",
    "",
    `Case: ${history.content_case_id}`,
    `Generated: ${history.generated_at}`,
    `Events: ${history.summary.event_count}`,
    `Truncated: ${history.truncated ? "yes" : "no"}`,
    "",
    "## Timeline",
    "",
  ];

  for (const event of history.events) {
    lines.push(
      `- ${event.at} | ${event.kind} | ${event.stage} | ${event.status}`
      + (event.locale ? ` | ${event.locale}` : "")
      + (event.attempt !== null ? ` | attempt=${event.attempt}` : "")
      + (event.error_code ? ` | error=${event.error_code}` : "")
      + (event.decision ? ` | decision=${event.decision}` : "")
      + (event.result ? ` | result=${event.result}` : "")
      + (event.reason_code ? ` | reason=${event.reason_code}` : "")
      + (typeof event.provider_call_count === "number"
        ? ` | provider_calls=${event.provider_call_count}`
        : "")
      + (typeof event.pages_read === "number"
        ? ` | pages_read=${event.pages_read}`
        : "")
      + (event.run_id ? ` | run=${event.run_id}` : "")
      + (event.step_run_id ? ` | step=${event.step_run_id}` : "")
      + (event.artifact_id ? ` | artifact=${event.artifact_id}` : ""),
    );
  }

  lines.push(
    "",
    "Safety: this report is generated from the sanitized history projection. "
      + "It excludes raw prompts, raw source/provider payloads, request bodies, "
      + "cookies, secrets, PII and raw error messages.",
  );
  return lines.join("\n");
}

function HistoryRow({ event }: { event: OperatorHistoryEvent }) {
  return (
    <li className="operator-history-item">
      <div className={"operator-history-marker " + eventClass(event)} aria-hidden="true" />
      <div className="operator-history-copy">
        <div className="operator-history-heading">
          <strong>{eventTitle(event)}</strong>
          <span className={"operator-history-status " + eventClass(event)}>
            {statusLabel(event.status)}
          </span>
        </div>
        <p>{eventSummary(event)}</p>
        <small>
          {formatTime(event.at)}
          {event.locale ? ` · ${event.locale}` : ""}
          {event.attempt !== null ? ` · lần ${event.attempt}` : ""}
        </small>
        <details className="operator-technical-details operator-history-details">
          <summary>Chi tiết kỹ thuật</summary>
          <dl>
            <div><dt>Loại</dt><dd>{event.kind}</dd></div>
            <div><dt>Bước</dt><dd>{event.stage}</dd></div>
            <div><dt>Trạng thái</dt><dd>{event.status}</dd></div>
            {event.error_code ? <div><dt>Mã lỗi</dt><dd>{event.error_code}</dd></div> : null}
            {event.reason_code ? (
              <div><dt>Lý do</dt><dd>{event.reason_code}</dd></div>
            ) : null}
            {typeof event.provider_call_count === "number" ? (
              <div><dt>Lượt provider</dt><dd>{event.provider_call_count}</dd></div>
            ) : null}
            {typeof event.pages_read === "number" ? (
              <div><dt>Trang đã đọc</dt><dd>{event.pages_read}</dd></div>
            ) : null}
            {event.run_id ? <div><dt>Run</dt><dd>{event.run_id}</dd></div> : null}
            {event.step_run_id ? <div><dt>Step</dt><dd>{event.step_run_id}</dd></div> : null}
            {event.artifact_id ? <div><dt>Artifact</dt><dd>{event.artifact_id}</dd></div> : null}
            {event.artifact_hash ? <div><dt>Hash</dt><dd>{event.artifact_hash}</dd></div> : null}
            {event.model ? (
              <div><dt>Model</dt><dd>{event.provider} / {event.model}</dd></div>
            ) : null}
            {event.input_tokens !== null || event.output_tokens !== null ? (
              <div>
                <dt>Token đã ghi nhận</dt>
                <dd>{event.input_tokens ?? "—"} vào · {event.output_tokens ?? "—"} ra</dd>
              </div>
            ) : null}
            {event.cost !== null ? (
              <div><dt>Chi phí đã ghi nhận</dt><dd>{event.cost}</dd></div>
            ) : null}
          </dl>
        </details>
      </div>
    </li>
  );
}

export function OperatorCaseHistoryPanel({ caseId }: { caseId: string }) {
  const [history, setHistory] = useState<OperatorCaseHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const applyHistory = useCallback(
    (nextHistory: OperatorCaseHistory) => {
      setHistory(nextHistory);
      setError("");
      setLoading(false);
    },
    [],
  );

  const applyHistoryError = useCallback((requestError: unknown) => {
    setError(
      requestError instanceof Error
        ? requestError.message
        : "Không tải được nhật ký bài viết.",
    );
    setLoading(false);
  }, []);

  const refreshHistory = useCallback(async () => {
    setLoading(true);
    try {
      applyHistory(await loadOperatorCaseHistory(caseId));
    } catch (requestError) {
      applyHistoryError(requestError);
    }
  }, [applyHistory, applyHistoryError, caseId]);

  useEffect(() => {
    let active = true;
    void loadOperatorCaseHistory(caseId).then(
      (nextHistory) => {
        if (active) applyHistory(nextHistory);
      },
      (requestError: unknown) => {
        if (active) applyHistoryError(requestError);
      },
    );
    return () => {
      active = false;
    };
  }, [applyHistory, applyHistoryError, caseId]);

  const recent = useMemo(
    () => [...(history?.events ?? [])].slice(-RECENT_COUNT).reverse(),
    [history],
  );
  const older = useMemo(
    () => [...(history?.events ?? [])].slice(0, -RECENT_COUNT).reverse(),
    [history],
  );

  return (
    <section className="operator-panel operator-history-panel" aria-busy={loading}>
      <div className="operator-panel-heading">
        <div>
          <p className="eyebrow">Nhật ký vận hành · tham khảo</p>
          <h2>Hệ thống đã làm gì?</h2>
          <p className="operator-note">
            Phần này chỉ phục vụ đối soát khi cần. Nội dung nguồn, prompt, dữ liệu riêng
            và thông tin xác thực không xuất hiện trong nhật ký này.
          </p>
        </div>
        <button
          className="operator-button secondary"
          disabled={loading}
          onClick={() => void refreshHistory()}
          type="button"
        >
          {loading ? "Đang tải…" : "Làm mới nhật ký"}
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {history ? (
        <>
          <div className="operator-history-summary" aria-label="Tóm tắt nhật ký">
            <span><strong>{history.summary.event_count}</strong> sự kiện</span>
            <span><strong>{history.summary.step_count}</strong> bước xử lý</span>
            <span><strong>{history.summary.approval_count}</strong> lần duyệt</span>
            <span><strong>{history.summary.failed_count}</strong> lỗi/chặn</span>
          </div>

          {recent.length > 0 ? (
            <ol className="operator-history-list">
              {recent.map((event) => <HistoryRow event={event} key={event.id} />)}
            </ol>
          ) : (
            <p className="operator-block-note">Chưa có hoạt động nào được ghi cho bài này.</p>
          )}

          {older.length > 0 ? (
            <details className="operator-history-all">
              <summary>Xem toàn bộ nhật ký ({history.events.length})</summary>
              <ol className="operator-history-list">
                {older.map((event) => <HistoryRow event={event} key={event.id} />)}
              </ol>
            </details>
          ) : null}

          {history.truncated ? (
            <p className="operator-block-note">
              Nhật ký rất dài; màn hình chỉ trả tối đa 500 sự kiện gần nhất.
            </p>
          ) : null}

          <details className="operator-history-export">
            <summary>Xuất báo cáo để phân tích lỗi</summary>
            <p>
              Báo cáo chỉ chứa các trường allowlist từ projection này. Hãy gửi file này
              khi cần MG phân tích một lần vận hành thật.
            </p>
            <div className="operator-home-actions">
              <button
                className="operator-button secondary"
                onClick={() => downloadFile(
                  `contentengine-support-${caseId.slice(0, 8)}.json`,
                  JSON.stringify(history, null, 2),
                  "application/json",
                )}
                type="button"
              >
                Tải JSON
              </button>
              <button
                className="operator-button secondary"
                onClick={() => downloadFile(
                  `contentengine-support-${caseId.slice(0, 8)}.md`,
                  supportMarkdown(history),
                  "text/markdown",
                )}
                type="button"
              >
                Tải Markdown
              </button>
            </div>
          </details>
        </>
      ) : null}
    </section>
  );
}
