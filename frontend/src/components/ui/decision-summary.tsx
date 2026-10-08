import type { ReactNode } from "react";

import styles from "./decision-summary.module.css";

type DecisionSummaryProps = {
  status: ReactNode;
  reason: ReactNode;
  nextAction: ReactNode;
  technicalDetails?: ReactNode;
  technicalLabel?: string;
};

export function DecisionSummary({
  status,
  reason,
  nextAction,
  technicalDetails,
  technicalLabel = "Chi tiết kỹ thuật",
}: DecisionSummaryProps) {
  return (
    <section className={styles.summary} aria-label="Tóm tắt quyết định">
      <div className={styles.businessLayer}>
        <div className={styles.businessItem}>
          <span className={styles.label}>Trạng thái</span>
          <div className={styles.value}>{status}</div>
        </div>
        <div className={styles.businessItem}>
          <span className={styles.label}>Vì sao</span>
          <div className={styles.value}>{reason}</div>
        </div>
        <div className={styles.businessItem}>
          <span className={styles.label}>Việc nên làm</span>
          <div className={styles.value}>{nextAction}</div>
        </div>
      </div>

      {technicalDetails ? (
        <details className={styles.technicalDetails}>
          <summary>{technicalLabel}</summary>
          <div className={styles.technicalBody}>{technicalDetails}</div>
        </details>
      ) : null}
    </section>
  );
}
