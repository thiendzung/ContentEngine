"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  approveAngle,
  loadOperatorCaseView,
  OperatorApiError,
  submitOperatorIntent,
  type AngleCandidate,
  type OperatorCaseView,
  type OperatorIntent,
} from "../../lib/operator/journal-api";
import {
  clearIdempotencyKey,
  getOrCreateIdempotencyKey,
} from "../../lib/operator/idempotency";
import {
  blockerAction,
  humanGateLabel,
  operatorPhaseLabel,
  operatorStatusLabel,
} from "../../lib/operator/operator-labels";

const POLL_MS = 2500;

function shortId(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function localeLabel(value: string): string {
  if (value === "vi") return "VI";
  if (value === "en") return "EN";
  return value.toUpperCase();
}

function mutationKey(caseId: string, stateVersion: string, action: string): string {
  return `operator:${caseId}:${stateVersion}:${action}`;
}

function technicalError(error: unknown): string {
  if (error instanceof OperatorApiError && error.code === "operator_state_stale") {
    return "Trạng thái đã thay đổi. Đã tải lại dữ liệu mới nhất.";
  }
  return error instanceof Error ? error.message : "Không thể hoàn tất thao tác.";
}

function AngleCard({
  candidate,
  selected,
  onSelect,
}: {
  candidate: AngleCandidate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article className={selected ? "angle-card selected" : "angle-card"}>
      <button className="angle-card-select" onClick={onSelect} type="button">
        <span className="angle-choice" aria-hidden="true">{selected ? "●" : "○"}</span>
        <span>
          <small>Góc {candidate.angle_id}</small>
          <strong>{candidate.working_title}</strong>
        </span>
      </button>
      <dl className="angle-facts">
        <div><dt>Vấn đề của độc giả</dt><dd>{candidate.reader_problem}</dd></div>
        <div><dt>Câu hỏi trung tâm</dt><dd>{candidate.central_question}</dd></div>
        <div><dt>Lời hứa</dt><dd>{candidate.core_promise}</dd></div>
        <div><dt>Góc nhìn</dt><dd>{candidate.point_of_view}</dd></div>
        <div><dt>Vì sao lúc này</dt><dd>{candidate.why_now}</dd></div>
      </dl>
      <div className="angle-meta-row">
        <span>Độ tin cậy {Math.round(candidate.confidence * 100)}%</span>
        <span>{localeLabel(candidate.locale)}</span>
      </div>
      {candidate.risks.length > 0 && (
        <div className="angle-risks">
          <span className="label">Rủi ro cần giữ</span>
          <ul>{candidate.risks.map((risk) => <li key={risk}>{risk}</li>)}</ul>
        </div>
      )}
      <details className="operator-technical-details">
        <summary>Nguồn & binding kỹ thuật</summary>
        <dl>
          <div><dt>Candidate hash</dt><dd>{candidate.candidate_hash}</dd></div>
          <div><dt>Evidence</dt><dd>{candidate.evidence_refs.join(", ")}</dd></div>
          <div><dt>Tư liệu MOTGU</dt><dd>{candidate.originality_refs.join(", ")}</dd></div>
          <div><dt>Không được khẳng định</dt><dd>{candidate.excluded_claims.join(" · ") || "—"}</dd></div>
        </dl>
      </details>
    </article>
  );
}

export function OperatorCaseWorkspace({ caseId }: { caseId: string }) {
  const [view, setView] = useState<OperatorCaseView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [selectedAngleId, setSelectedAngleId] = useState("");
  const [comment, setComment] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const result = await loadOperatorCaseView(caseId);
      setView(result);
      setError("");
    } catch (requestError) {
      setError(technicalError(requestError));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    let cancelled = false;
    loadOperatorCaseView(caseId)
      .then((result) => {
        if (cancelled) return;
        setView(result);
        setError("");
        setLoading(false);
      })
      .catch((requestError: unknown) => {
        if (cancelled) return;
        setError(technicalError(requestError));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useEffect(() => {
    if (!view || !["QUEUED", "RUNNING"].includes(view.state.status)) return;
    const timer = window.setInterval(() => void refresh(true), POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh, view]);

  const angleGate = view?.pending_gate?.type === "angle" ? view.pending_gate : null;
  const selectedAngle = useMemo(
    () => angleGate?.candidates.find((item) => item.angle_id === selectedAngleId) ?? null,
    [angleGate, selectedAngleId],
  );

  async function submitIntent(intent: OperatorIntent) {
    if (!view || submitting || !view.state.allowed_intents.includes(intent)) return;
    const keyScope = mutationKey(caseId, view.state.state_version, intent);
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await submitOperatorIntent(caseId, {
        intent,
        expected_state_version: view.state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
      });
      clearIdempotencyKey(keyScope);
      setNotice(intent === "start" ? "Đã xếp tác vụ vào hàng đợi." : "Đã ghi yêu cầu thử lại.");
      await refresh(true);
    } catch (requestError) {
      if (requestError instanceof OperatorApiError && requestError.code === "operator_state_stale") {
        clearIdempotencyKey(keyScope);
        await refresh(true);
      }
      setError(technicalError(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitAngleApproval() {
    if (!view || !angleGate || !selectedAngle || submitting) return;
    const state = view.state;
    const artifact = angleGate.artifact;
    const keyScope = mutationKey(
      caseId,
      state.state_version,
      `approve-angle:${selectedAngle.angle_id}`,
    );
    if (!window.confirm(`Duyệt góc “${selectedAngle.working_title}”?`)) return;
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await approveAngle(caseId, {
        expected_state_version: state.state_version,
        idempotency_key: getOrCreateIdempotencyKey(keyScope),
        artifact_id: artifact.id,
        artifact_version: artifact.version,
        artifact_hash: artifact.content_hash,
        selected_angle_id: selectedAngle.angle_id,
        selected_candidate_hash: selectedAngle.candidate_hash,
        comment: comment.trim() || null,
      });
      clearIdempotencyKey(keyScope);
      setSelectedAngleId("");
      setComment("");
      setNotice("Angle đã được duyệt theo đúng snapshot. UI-01 dừng tại cổng này.");
      await refresh(true);
    } catch (requestError) {
      if (requestError instanceof OperatorApiError && requestError.code === "operator_state_stale") {
        clearIdempotencyKey(keyScope);
        await refresh(true);
      }
      setError(technicalError(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !view) {
    return <main className="operator-page"><p className="loading">Đang tải Journal…</p></main>;
  }

  if (!view) {
    return (
      <main className="operator-page">
        <p className="error">{error || "Không tìm thấy Journal."}</p>
        <Link className="operator-link" href="/operator">Quay lại điều hành</Link>
      </main>
    );
  }

  const state = view.state;
  const canStart = state.status === "READY" && state.allowed_intents.includes("start");
  const canRetry = state.allowed_intents.includes("retry");

  return (
    <main className="operator-page">
      <header className="operator-case-header">
        <div>
          <p className="eyebrow">Journal · {localeLabel(view.intake.source_locale)}</p>
          <h1>{view.question}</h1>
          <p className="intro">{view.promise}</p>
        </div>
        <div className="operator-header-state">
          <span className={`operator-state-badge ${state.status.toLowerCase()}`}>
            {operatorStatusLabel(state.status)}
          </span>
          <small>{operatorPhaseLabel(state.phase)}</small>
        </div>
      </header>

      <section className="operator-case-facts">
        <div><span>Độc giả</span><p>{view.reader}</p></div>
        <div><span>Tình huống</span><p>{view.situation}</p></div>
        <div><span>Nhu cầu</span><p>{view.need}</p></div>
        <div>
          <span>Ngôn ngữ yêu cầu</span>
          <p>{view.intake.required_locales.map((item) => `${localeLabel(item.locale)} · ${item.role}`).join(" / ")}</p>
        </div>
      </section>

      {notice && <p className="operator-success">{notice}</p>}
      {error && <p className="error">{error}</p>}

      <section className="operator-panel state-panel">
        <div className="operator-panel-heading">
          <div>
            <p className="eyebrow">Trạng thái chuẩn</p>
            <h2>{operatorStatusLabel(state.status)}</h2>
          </div>
          <button className="operator-button secondary" onClick={() => void refresh()} type="button">
            Tải lại
          </button>
        </div>
        <div className="state-grid">
          <div><span>Giai đoạn</span><strong>{operatorPhaseLabel(state.phase)}</strong></div>
          <div><span>Cổng duyệt</span><strong>{humanGateLabel(state.human_gate)}</strong></div>
          <div><span>Run</span><strong>{shortId(state.current_run_id)}</strong></div>
          <div><span>Step</span><strong>{shortId(state.current_step_run_id)}</strong></div>
        </div>

        {canStart && (
          <div className="operator-primary-action">
            <div>
              <strong>Bắt đầu sản xuất</strong>
              <p>Backend sẽ tự quyết stage/provider/model; UI chỉ gửi ý định Start.</p>
            </div>
            <button
              className="operator-button primary"
              disabled={submitting}
              onClick={() => void submitIntent("start")}
              type="button"
            >
              {submitting ? "Đang gửi…" : "Bắt đầu"}
            </button>
          </div>
        )}

        {["QUEUED", "RUNNING"].includes(state.status) && (
          <div className="operator-running-state">
            <span className="activity-pulse" aria-hidden="true" />
            <div>
              <strong>{state.status === "QUEUED" ? "Đang chờ worker" : "Đang xử lý"}</strong>
              <p>Trang tự tải lại trạng thái khoảng 2,5 giây/lần. Có thể refresh trình duyệt an toàn.</p>
            </div>
          </div>
        )}

        {state.status === "BLOCKED" && (
          <div className="operator-blocker">
            <strong>{state.blocker_message ?? "Workflow đang bị chặn."}</strong>
            <p>{blockerAction(state)}</p>
            {canRetry && (
              <button
                className="operator-button secondary"
                disabled={submitting}
                onClick={() => void submitIntent("retry")}
                type="button"
              >
                Thử lại
              </button>
            )}
          </div>
        )}
      </section>

      {state.status === "AWAITING_APPROVAL" && state.human_gate === "angle" && angleGate && (
        <section className="operator-panel angle-review-panel">
          <div className="operator-panel-heading">
            <div>
              <p className="eyebrow">Cổng duyệt 1/3</p>
              <h2>Chọn góc tiếp cận</h2>
            </div>
            <span className="operator-note">Chọn một candidate đã được backend khóa hash.</span>
          </div>
          <div className="angle-grid">
            {angleGate.candidates.map((candidate) => (
              <AngleCard
                candidate={candidate}
                key={candidate.angle_id}
                onSelect={() => setSelectedAngleId(candidate.angle_id)}
                selected={selectedAngleId === candidate.angle_id}
              />
            ))}
          </div>
          <div className="angle-approval-bar">
            <label>
              <span>Ghi chú duyệt (không bắt buộc)</span>
              <textarea
                onChange={(event) => setComment(event.target.value)}
                placeholder="Lý do chọn góc này…"
                rows={3}
                value={comment}
              />
            </label>
            <button
              className="operator-button primary"
              disabled={!selectedAngle || submitting}
              onClick={() => void submitAngleApproval()}
              type="button"
            >
              {submitting ? "Đang lưu…" : "Duyệt Angle"}
            </button>
          </div>
          <details className="operator-technical-details artifact-details">
            <summary>Snapshot Angle</summary>
            <dl>
              <div><dt>Artifact</dt><dd>{angleGate.artifact.id}</dd></div>
              <div><dt>Version</dt><dd>{angleGate.artifact.version}</dd></div>
              <div><dt>Hash</dt><dd>{angleGate.artifact.content_hash}</dd></div>
              <div><dt>State version</dt><dd>{state.state_version}</dd></div>
            </dl>
          </details>
        </section>
      )}

      {state.status === "AWAITING_APPROVAL" && state.human_gate !== "angle" && (
        <section className="operator-panel">
          <p className="operator-block-note">
            Workflow đã tới {humanGateLabel(state.human_gate)}. UI-01 chỉ triển khai tới Angle.
          </p>
        </section>
      )}

      <footer className="operator-footer-links">
        <Link className="operator-link" href="/operator">Điều hành</Link>
        <Link className="operator-link" href="/production">Bảng sản xuất</Link>
      </footer>
    </main>
  );
}