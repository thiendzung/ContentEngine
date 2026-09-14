"use client";

import { useCallback, useEffect, useState } from "react";

import {
  loadOperatorPreflight,
  type OperatorPreflight,
} from "../../lib/operator/journal-api";
import { preflightDetail, preflightLabel } from "../../lib/operator/operator-labels";

type Props = {
  onReadyChange?: (ready: boolean) => void;
};

export function PreflightStatus({ onReadyChange }: Props) {
  const [preflight, setPreflight] = useState<OperatorPreflight | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await loadOperatorPreflight();
      setPreflight(result);
      setError("");
      onReadyChange?.(result.status === "READY");
    } catch (requestError) {
      setPreflight(null);
      setError(
        requestError instanceof Error ? requestError.message : "Không tải được preflight.",
      );
      onReadyChange?.(false);
    } finally {
      setLoading(false);
    }
  }, [onReadyChange]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="operator-panel operator-preflight" aria-live="polite">
      <div className="operator-panel-heading">
        <div>
          <p className="eyebrow">Preflight</p>
          <h2>Trạng thái hệ thống</h2>
        </div>
        <button className="operator-button secondary" onClick={() => void refresh()} type="button">
          Kiểm tra lại
        </button>
      </div>

      {loading && <p className="loading">Đang kiểm tra hệ thống…</p>}
      {error && <p className="error">{error}</p>}

      {preflight && (
        <>
          <div className={`operator-readiness ${preflight.status.toLowerCase()}`}>
            <strong>{preflight.status === "READY" ? "READY" : "BLOCKED"}</strong>
            <span>
              {preflight.status === "READY"
                ? "Hệ thống sẵn sàng nhận tác vụ mới."
                : "Có điều kiện bắt buộc chưa sẵn sàng."}
            </span>
          </div>
          <div className="preflight-grid">
            {preflight.checks.map((check) => (
              <article className="preflight-check" key={check.key}>
                <span className={`status-dot ${check.status.toLowerCase()}`} aria-hidden="true" />
                <div>
                  <strong>{preflightLabel(check.key)}</strong>
                  <small>{preflightDetail(check)}</small>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
