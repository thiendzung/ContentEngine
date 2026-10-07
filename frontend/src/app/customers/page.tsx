"use client";

import { useEffect, useRef, useState } from "react";

import {
  type CustomerAudienceDetail,
  type CustomerInsight,
  type CustomerMapChanges,
  type CustomerMapSummary,
  type CustomerNeed,
  type CustomerNeedDetail,
  loadCustomerAudience,
  loadCustomerMapChanges,
  loadCustomerMapSummary,
  loadCustomerNeed,
} from "../../lib/api/customer-intelligence";
import {
  customerChangeKindLabel,
  customerEntityTypeLabel,
  customerInsightTypeLabel,
  customerJourneyStageLabel,
  customerNeedTypeLabel,
  customerOriginLabel,
  customerRelationLabel,
} from "../../lib/ui/vi/customer";
import { uiStatusLabel } from "../../lib/ui/vi/status";
import styles from "../intelligence.module.css";

const PROJECT_SLUG = "motgu";
const SNAPSHOT_DRIFT_PREFIX = "customer_map_snapshot_changed_during_read:";

type CustomerViewState = {
  summary: CustomerMapSummary;
  changes: CustomerMapChanges;
  audience: CustomerAudienceDetail | null;
  needDetail: CustomerNeedDetail | null;
  selectedAudienceId: string;
  selectedNeedId: string;
};

function assertSnapshotHash(
  expected: string,
  actual: string,
  scope: string,
) {
  if (expected !== actual) {
    throw new Error(SNAPSHOT_DRIFT_PREFIX + scope);
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function isSnapshotDrift(error: unknown): boolean {
  return (
    error instanceof Error &&
    error.message.startsWith(SNAPSHOT_DRIFT_PREFIX)
  );
}

function statusClass(value: string): string {
  if (value === "SUPPORTED" || value === "ACTIVE") {
    return styles.badgePositive;
  }
  if (value === "REJECTED") return styles.badgeNegative;
  if (
    value === "PROPOSED" ||
    value === "CANDIDATE" ||
    value === "TESTING" ||
    value === "INSUFFICIENT_EVIDENCE"
  ) {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function EvidenceSummary({
  supports,
  contradicts,
  independentSupports,
  independentContradicts,
  context,
  independentContext,
}: {
  supports: number;
  contradicts: number;
  independentSupports: number;
  independentContradicts: number;
  context?: number;
  independentContext?: number;
}) {
  return (
    <div className={styles.evidence}>
      <span className={styles.badgePositive}>
        Ủng hộ {supports} · độc lập {independentSupports}
      </span>
      <span className={contradicts > 0 ? styles.badgeNegative : styles.badge}>
        Mâu thuẫn {contradicts} · độc lập {independentContradicts}
      </span>
      {context !== undefined ? (
        <span className={styles.badge}>
          Bối cảnh {context} · độc lập {independentContext ?? 0}
        </span>
      ) : null}
    </div>
  );
}

function SignalRefs({
  insight,
}: {
  insight: CustomerInsight;
}) {
  const refs = [
    ...insight.signal_refs.supports.map((id) => ({
      id,
      relation: "supports",
    })),
    ...insight.signal_refs.contradicts.map((id) => ({
      id,
      relation: "contradicts",
    })),
    ...(insight.signal_refs.context ?? []).map((id) => ({
      id,
      relation: "context",
    })),
  ];

  return (
    <div className={styles.signalList}>
      {refs.length === 0 ? (
        <span>Chưa có tín hiệu được liên kết.</span>
      ) : (
        refs.map((ref) => (
          <span key={ref.relation + ":" + ref.id}>
            {customerRelationLabel(ref.relation)} · {ref.id}
          </span>
        ))
      )}
    </div>
  );
}

function NeedCard({
  need,
  active,
  disabled,
  onSelect,
}: {
  need: CustomerNeed;
  active: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={
        styles.listButton + " " + (active ? styles.listButtonActive : "")
      }
      onClick={onSelect}
      aria-pressed={active}
      disabled={disabled}
    >
      <strong>{need.statement}</strong>
      <small>
        {uiStatusLabel(need.status)} · {customerNeedTypeLabel(need.type)} · v{need.version}
      </small>
    </button>
  );
}

function InsightCard({ insight }: { insight: CustomerInsight }) {
  return (
    <article className={styles.card}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">
            Nhận định khách hàng · {customerInsightTypeLabel(insight.insight_type)}
          </p>
          <h3>{insight.statement}</h3>
        </div>
        <span className={statusClass(insight.status)}>
          {uiStatusLabel(insight.status)}
        </span>
      </div>

      {insight.situation ? <p>{insight.situation}</p> : null}

      <EvidenceSummary
        supports={insight.evidence_counts.supports}
        contradicts={insight.evidence_counts.contradicts}
        independentSupports={insight.evidence_counts.independent_supports}
        independentContradicts={insight.evidence_counts.independent_contradicts}
        context={insight.evidence_counts.context}
        independentContext={insight.evidence_counts.independent_context}
      />

      <dl className={styles.definition}>
        <dt>Phiên bản</dt>
        <dd>v{insight.version}</dd>
        <dt>Trạng thái duyệt</dt>
        <dd>{uiStatusLabel(insight.status)}</dd>
        <dt>Người duyệt</dt>
        <dd>{insight.reviewed_by ?? "Chưa có"}</dd>
        <dt>Lý do duyệt</dt>
        <dd>{insight.review_reason ?? "Chưa có"}</dd>
        <dt>Quan sát / suy luận</dt>
        <dd>Chưa có trường dữ liệu riêng trong quy ước hiện tại.</dd>
      </dl>

      <div className={styles.evidenceBlock}>
        <strong>Tham chiếu tín hiệu</strong>
        <SignalRefs insight={insight} />
      </div>

      {insight.need_links.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Liên kết nhu cầu</strong>
          <ul>
            {insight.need_links.map((link) => (
              <li
                key={
                  link.need_hypothesis_id +
                  ":" +
                  link.relation +
                  ":" +
                  link.linked_by
                }
              >
                {customerRelationLabel(link.relation)} · {link.reason}
                <span className={styles.meta}>
                  {" "}
                  ({link.need_hypothesis_id})
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {insight.alternative_explanations.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Giải thích thay thế</strong>
          <ul>
            {insight.alternative_explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {insight.missing_evidence.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Bằng chứng còn thiếu</strong>
          <ul>
            {insight.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

function NeedDetail({ detail }: { detail: CustomerNeedDetail }) {
  const need = detail.need;

  return (
    <section className={styles.panel}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">Nhu cầu · {customerNeedTypeLabel(need.type)}</p>
          <h2>{need.statement}</h2>
        </div>
        <span className={statusClass(need.status)}>
          {uiStatusLabel(need.status)}
        </span>
      </div>

      <dl className={styles.definition}>
        <dt>Nguồn hình thành</dt>
        <dd>{customerOriginLabel(need.origin)}</dd>
        <dt>Phạm vi nhóm khách hàng</dt>
        <dd>{need.audience_scope ?? "Không có giá trị riêng"}</dd>
        <dt>Tình huống</dt>
        <dd>{need.situation ?? "Không có giá trị riêng"}</dd>
        <dt>Phiên bản</dt>
        <dd>v{need.version}</dd>
        <dt>Trạng thái duyệt</dt>
        <dd>{uiStatusLabel(need.status)}</dd>
        <dt>Người duyệt</dt>
        <dd>{need.reviewed_by ?? "Chưa có"}</dd>
        <dt>Lý do duyệt</dt>
        <dd>{need.review_reason ?? "Chưa có"}</dd>
      </dl>

      <div className={styles.evidenceBlock}>
        <strong>Bằng chứng</strong>
        <EvidenceSummary
          supports={need.evidence_counts.supports}
          contradicts={need.evidence_counts.contradicts}
          independentSupports={need.evidence_counts.independent_supports}
          independentContradicts={need.evidence_counts.independent_contradicts}
        />
        <div className={styles.signalList}>
          {need.signal_refs.supports.map((id) => (
            <span key={"supports:" + id}>Ủng hộ · {id}</span>
          ))}
          {need.signal_refs.contradicts.map((id) => (
            <span key={"contradicts:" + id}>Mâu thuẫn · {id}</span>
          ))}
          {need.signal_refs.supports.length === 0 &&
          need.signal_refs.contradicts.length === 0 ? (
            <span>Chưa có tín hiệu được liên kết.</span>
          ) : null}
        </div>
      </div>

      {need.insight_links.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Quan hệ Nhu cầu ↔ Nhận định khách hàng</strong>
          <ul>
            {need.insight_links.map((link) => (
              <li
                key={
                  link.customer_insight_id +
                  ":" +
                  link.relation +
                  ":" +
                  link.linked_by
                }
              >
                {customerRelationLabel(link.relation)} · {link.reason}
                <span className={styles.meta}>
                  {" "}
                  ({link.customer_insight_id})
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {need.alternative_explanations.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Giải thích thay thế</strong>
          <ul>
            {need.alternative_explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {need.missing_evidence.length > 0 ? (
        <div className={styles.evidenceBlock}>
          <strong>Bằng chứng còn thiếu</strong>
          <ul>
            {need.missing_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className={styles.evidenceBlock}>
        <strong>Nhận định liên quan</strong>
        {detail.insights.length === 0 ? (
          <p>Chưa có nhận định khách hàng được liên kết với nhu cầu này.</p>
        ) : (
          <div className={styles.cards}>
            {detail.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

async function loadCustomerView(
  preferredAudienceId = "",
  preferredNeedId = "",
): Promise<CustomerViewState> {
  const [summary, changes] = await Promise.all([
    loadCustomerMapSummary(PROJECT_SLUG),
    loadCustomerMapChanges(PROJECT_SLUG),
  ]);

  assertSnapshotHash(
    summary.snapshot_hash,
    changes.current_snapshot_hash,
    "changes",
  );

  const selectedAudienceId =
    preferredAudienceId &&
    summary.audiences.some((item) => item.id === preferredAudienceId)
      ? preferredAudienceId
      : summary.audiences[0]?.id ?? "";

  const audience = selectedAudienceId
    ? await loadCustomerAudience(selectedAudienceId, PROJECT_SLUG)
    : null;

  if (audience) {
    assertSnapshotHash(
      summary.snapshot_hash,
      audience.snapshot_hash,
      "audience",
    );
  }

  const selectedNeedId =
    audience &&
    preferredNeedId &&
    audience.needs.some((item) => item.id === preferredNeedId)
      ? preferredNeedId
      : audience?.needs[0]?.id ?? "";

  const needDetail = selectedNeedId
    ? await loadCustomerNeed(selectedNeedId, PROJECT_SLUG)
    : null;

  if (needDetail) {
    assertSnapshotHash(
      summary.snapshot_hash,
      needDetail.snapshot_hash,
      "need",
    );
  }

  return {
    summary,
    changes,
    audience,
    needDetail,
    selectedAudienceId,
    selectedNeedId,
  };
}

export default function CustomersPage() {
  const [view, setView] = useState<CustomerViewState | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [staleMessage, setStaleMessage] = useState("");
  const requestVersion = useRef(0);

  useEffect(() => {
    const requestId = ++requestVersion.current;
    let cancelled = false;

    async function loadInitial() {
      setLoading(true);
      setError("");
      try {
        const nextView = await loadCustomerView();
        if (cancelled || requestId !== requestVersion.current) return;
        setView(nextView);
      } catch (nextError) {
        if (cancelled || requestId !== requestVersion.current) return;
        setError(
          errorMessage(nextError, "Không thể tải Bản đồ khách hàng."),
        );
      } finally {
        if (!cancelled && requestId === requestVersion.current) {
          setLoading(false);
        }
      }
    }

    void loadInitial();

    return () => {
      cancelled = true;
      requestVersion.current += 1;
    };
  }, []);

  const selectedAudienceSummary =
    view?.summary.audiences.find(
      (item) => item.id === view.selectedAudienceId,
    ) ?? null;

  async function selectAudience(audienceId: string) {
    if (!view || loading || detailLoading) return;

    const requestId = ++requestVersion.current;
    setDetailLoading(true);
    setError("");

    try {
      const nextAudience = await loadCustomerAudience(
        audienceId,
        PROJECT_SLUG,
      );
      assertSnapshotHash(
        view.summary.snapshot_hash,
        nextAudience.snapshot_hash,
        "audience",
      );

      const firstNeed = nextAudience.needs[0] ?? null;
      const nextNeed = firstNeed
        ? await loadCustomerNeed(firstNeed.id, PROJECT_SLUG)
        : null;

      if (nextNeed) {
        assertSnapshotHash(
          view.summary.snapshot_hash,
          nextNeed.snapshot_hash,
          "need",
        );
      }

      if (requestId !== requestVersion.current) return;

      setView({
        ...view,
        audience: nextAudience,
        needDetail: nextNeed,
        selectedAudienceId: audienceId,
        selectedNeedId: firstNeed?.id ?? "",
      });
    } catch (nextError) {
      if (requestId !== requestVersion.current) return;
      if (isSnapshotDrift(nextError)) {
        setStaleMessage(
          "Bản đồ khách hàng đã thay đổi trong lúc đọc. Dữ liệu cũ được giữ nguyên; hãy bấm Làm mới để lấy một ảnh chụp nhất quán.",
        );
      } else {
        setError(errorMessage(nextError, "Không thể tải nhóm khách hàng."));
      }
    } finally {
      if (requestId === requestVersion.current) {
        setDetailLoading(false);
      }
    }
  }

  async function selectNeed(needId: string) {
    if (!view || loading || detailLoading) return;

    const requestId = ++requestVersion.current;
    setDetailLoading(true);
    setError("");

    try {
      const nextNeed = await loadCustomerNeed(needId, PROJECT_SLUG);
      assertSnapshotHash(
        view.summary.snapshot_hash,
        nextNeed.snapshot_hash,
        "need",
      );

      if (requestId !== requestVersion.current) return;

      setView({
        ...view,
        needDetail: nextNeed,
        selectedNeedId: needId,
      });
    } catch (nextError) {
      if (requestId !== requestVersion.current) return;
      if (isSnapshotDrift(nextError)) {
        setStaleMessage(
          "Bản đồ khách hàng đã thay đổi trong lúc đọc. Dữ liệu cũ được giữ nguyên; hãy bấm Làm mới để lấy một ảnh chụp nhất quán.",
        );
      } else {
        setError(errorMessage(nextError, "Không thể tải nhu cầu."));
      }
    } finally {
      if (requestId === requestVersion.current) {
        setDetailLoading(false);
      }
    }
  }

  async function refresh() {
    if (loading || detailLoading) return;

    const requestId = ++requestVersion.current;
    setLoading(true);
    setError("");
    setStaleMessage("");

    try {
      const nextView = await loadCustomerView(
        view?.selectedAudienceId ?? "",
        view?.selectedNeedId ?? "",
      );
      if (requestId !== requestVersion.current) return;
      setView(nextView);
    } catch (nextError) {
      if (requestId !== requestVersion.current) return;
      const message = errorMessage(
        nextError,
        "Không thể làm mới Bản đồ khách hàng.",
      );
      if (view) {
        setStaleMessage(
          "Lần làm mới thất bại (" +
            message +
            "). Dữ liệu đang hiển thị là ảnh chụp thành công gần nhất.",
        );
      } else {
        setError(message);
      }
    } finally {
      if (requestId === requestVersion.current) {
        setLoading(false);
      }
    }
  }

  return (
    <main
      className={styles.page}
      aria-busy={loading || detailLoading}
    >
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Bản đồ khách hàng</p>
          <h1>Khách hàng</h1>
          <p className="intro">
            Xem nhóm khách hàng, nhu cầu, nhận định và bằng chứng đúng như hệ thống
            đang lưu. Màn hình này chỉ đọc dữ liệu.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refresh()}
            disabled={loading || detailLoading}
          >
            {loading || detailLoading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        Dữ liệu hiện tại chưa có cờ <strong>quan sát/suy luận</strong> riêng cho
        nhận định khách hàng. Giao diện không tự suy diễn; nó hiển thị riêng trạng thái
        duyệt, nguồn hình thành nhu cầu, người duyệt và bằng chứng mà hệ thống thực sự cung cấp.
      </div>

      {loading && !view ? (
        <div
          className={styles.loading}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          Đang tải Bản đồ khách hàng…
        </div>
      ) : null}

      {error ? (
        <div className={styles.error} role="alert" aria-atomic="true">
          Không thể đọc Bản đồ khách hàng: {error}
        </div>
      ) : null}

      {staleMessage ? (
        <div
          className={styles.notice + " " + styles.stale}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {staleMessage}
        </div>
      ) : null}

      {view ? (
        <>
          <section
            className={styles.stats}
            aria-label="Tổng quan Bản đồ khách hàng"
          >
            <div className={styles.stat}>
              <span>Nhóm khách hàng</span>
              <strong>{view.summary.counts.audiences}</strong>
            </div>
            <div className={styles.stat}>
              <span>Nhu cầu</span>
              <strong>{view.summary.counts.needs}</strong>
            </div>
            <div className={styles.stat}>
              <span>Nhận định</span>
              <strong>{view.summary.counts.insights}</strong>
            </div>
            <div className={styles.stat}>
              <span>Nhu cầu có bằng chứng hỗ trợ</span>
              <strong>{view.summary.counts.supported_needs}</strong>
            </div>
            <div className={styles.stat}>
              <span>Nhận định có bằng chứng hỗ trợ</span>
              <strong>{view.summary.counts.supported_insights}</strong>
            </div>
            <div className={styles.stat}>
              <span>Chưa gán</span>
              <strong>
                {view.summary.counts.unassigned_needs +
                  view.summary.counts.unassigned_insights}
              </strong>
            </div>
          </section>

          <p className={styles.hash}>
            Mã ảnh chụp: {view.summary.snapshot_hash}
          </p>

          <section className={styles.panel}>
            <div className={styles.sectionHeader}>
              <div>
                <p className="eyebrow">Hành trình khách hàng</p>
                <h2>Mô hình hành trình đang áp dụng</h2>
              </div>
            </div>
            <div className={styles.journeyChips}>
              {view.summary.journey.stages.map((stage) => (
                <span className={styles.badge} key={stage.key}>
                  {customerJourneyStageLabel(stage.key, stage.label)}
                </span>
              ))}
            </div>
            <p className={styles.meta}>
              Hành trình là mô hình cấu hình hoặc được suy ra. Bản đồ khách hàng hiện không
              lưu bền vững quan hệ Nhu cầu → Hành trình; giao diện không tự gán nhu cầu vào giai đoạn.
            </p>
          </section>

          {view.summary.audiences.length === 0 ? (
            <div className={styles.empty} role="status">
              Chưa có giả thuyết nhóm khách hàng trong Bản đồ khách hàng.
            </div>
          ) : (
            <div className={styles.grid}>
              <aside className={styles.sidebar}>
                <p className="label">Nhóm khách hàng</p>
                <div className={styles.list}>
                  {view.summary.audiences.map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      className={
                        styles.listButton +
                        " " +
                        (view.selectedAudienceId === item.id
                          ? styles.listButtonActive
                          : "")
                      }
                      onClick={() => void selectAudience(item.id)}
                      aria-pressed={view.selectedAudienceId === item.id}
                      disabled={loading || detailLoading}
                    >
                      <strong>{item.name}</strong>
                      <small>
                        {uiStatusLabel(item.status)} · {item.need_count} nhu cầu ·{" "}
                        {item.insight_count} nhận định
                      </small>
                    </button>
                  ))}
                </div>
              </aside>

              <div className={styles.cards}>
                {detailLoading ? (
                  <div
                    className={styles.loading}
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    Đang tải chi tiết…
                  </div>
                ) : null}

                {view.audience ? (
                  <section className={styles.panel}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">Giả thuyết nhóm khách hàng</p>
                        <h2>{view.audience.audience.name}</h2>
                      </div>
                      <span
                        className={statusClass(view.audience.audience.status)}
                      >
                        {uiStatusLabel(view.audience.audience.status)}
                      </span>
                    </div>
                    <p>
                      {view.audience.audience.description ??
                        "Hệ thống chưa lưu mô tả riêng cho nhóm khách hàng này."}
                    </p>
                    <dl className={styles.definition}>
                      <dt>Trạng thái</dt>
                      <dd>{uiStatusLabel(view.audience.audience.status)}</dd>
                      <dt>Độ tin cậy</dt>
                      <dd>
                        {view.audience.audience.confidence === null
                          ? "Chưa có"
                          : String(view.audience.audience.confidence)}
                      </dd>
                      <dt>Tóm tắt bằng chứng</dt>
                      <dd>
                        {view.audience.audience.evidence_summary ??
                          "Chưa có tóm tắt bằng chứng."}
                      </dd>
                      <dt>Nhu cầu</dt>
                      <dd>{view.audience.needs.length}</dd>
                      <dt>Nhận định</dt>
                      <dd>{view.audience.insights.length}</dd>
                    </dl>
                  </section>
                ) : null}

                {view.audience && view.audience.needs.length > 0 ? (
                  <section className={styles.panel}>
                    <div className={styles.sectionHeader}>
                      <div>
                        <p className="eyebrow">Bản đồ nhu cầu</p>
                        <h2>
                          Nhu cầu của{" "}
                          {selectedAudienceSummary?.name ?? "nhóm khách hàng"}
                        </h2>
                      </div>
                    </div>
                    <div className={styles.list}>
                      {view.audience.needs.map((need) => (
                        <NeedCard
                          key={need.id}
                          need={need}
                          active={view.selectedNeedId === need.id}
                          disabled={loading || detailLoading}
                          onSelect={() => void selectNeed(need.id)}
                        />
                      ))}
                    </div>
                  </section>
                ) : view.audience ? (
                  <div className={styles.empty} role="status">
                    Nhóm khách hàng này chưa có giả thuyết nhu cầu được gán.
                  </div>
                ) : null}

                {view.needDetail ? (
                  <NeedDetail detail={view.needDetail} />
                ) : null}

                {view.audience && view.audience.insights.length > 0 ? (
                  <section className={styles.panel}>
                    <p className="eyebrow">Nhận định theo nhóm khách hàng</p>
                    <h2>Nhận định được gán trực tiếp</h2>
                    <div className={styles.cards}>
                      {view.audience.insights.map((insight) => (
                        <InsightCard key={insight.id} insight={insight} />
                      ))}
                    </div>
                  </section>
                ) : view.audience ? (
                  <div className={styles.empty} role="status">
                    Nhóm khách hàng này chưa có nhận định khách hàng được gán trực tiếp.
                  </div>
                ) : null}

                <section className={styles.panel}>
                  <div className={styles.sectionHeader}>
                    <div>
                      <p className="eyebrow">Thay đổi gần đây</p>
                      <h2>Thay đổi so với ảnh chụp trước</h2>
                    </div>
                    <div className={styles.badges}>
                      <span className={styles.badge}>
                        MỚI {view.changes.counts.NEW}
                      </span>
                      <span className={styles.badgePositive}>
                        ỦNG HỘ {view.changes.counts.SUPPORT}
                      </span>
                      <span className={styles.badgeNegative}>
                        MÂU THUẪN {view.changes.counts.CONTRADICT}
                      </span>
                      <span className={styles.badge}>
                        TRÙNG {view.changes.counts.DUPLICATE}
                      </span>
                    </div>
                  </div>

                  <dl className={styles.definition}>
                    <dt>Ảnh chụp trước</dt>
                    <dd>
                      {view.changes.previous_snapshot_hash ?? "Không có"}
                    </dd>
                    <dt>Ảnh chụp hiện tại</dt>
                    <dd>{view.changes.current_snapshot_hash}</dd>
                  </dl>

                  {view.changes.baseline ? (
                    <p>
                      Chưa có ảnh chụp trước; đây là mốc nền đầu tiên, không
                      được diễn giải như thay đổi hành vi khách hàng.
                    </p>
                  ) : view.changes.events.length === 0 ? (
                    <p>Không có thay đổi giữa hai ảnh chụp được so sánh.</p>
                  ) : (
                    <div className={styles.changeList}>
                      {view.changes.events.slice(0, 20).map((event, index) => (
                        <div
                          className={styles.change}
                          key={
                            event.kind +
                            ":" +
                            event.entity_type +
                            ":" +
                            event.entity_ref +
                            ":" +
                            index
                          }
                        >
                          <strong>
                            {customerChangeKindLabel(event.kind)} · {customerEntityTypeLabel(event.entity_type)}
                          </strong>
                          <p>{event.detail}</p>
                          <small className={styles.meta}>
                            {event.entity_ref}
                          </small>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </div>
          )}
        </>
      ) : null}
    </main>
  );
}