"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type ContentCoverage,
  type CoverageStatus,
  loadContentCoverage,
} from "../../lib/api/customer-intelligence";
import styles from "../intelligence.module.css";

const PROJECT_SLUG = "motgu";
const STATUS_ORDER: CoverageStatus[] = [
  "MISSING",
  "PLANNED",
  "IN_PROGRESS",
  "PUBLISHED",
  "NEEDS_UPDATE",
  "WEAK",
  "INSUFFICIENT_DATA",
];

function coverageLabel(value: CoverageStatus): string {
  const labels: Record<CoverageStatus, string> = {
    MISSING: "Thiếu nội dung",
    PLANNED: "Đã lên kế hoạch",
    IN_PROGRESS: "Đang sản xuất",
    PUBLISHED: "Đã xuất bản",
    NEEDS_UPDATE: "Cần cập nhật",
    WEAK: "Nội dung yếu",
    INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  };
  return labels[value];
}

function coverageClass(value: CoverageStatus): string {
  if (value === "PUBLISHED") return styles.badgePositive;
  if (value === "WEAK" || value === "INSUFFICIENT_DATA") {
    return styles.badgeNegative;
  }
  if (
    value === "MISSING" ||
    value === "PLANNED" ||
    value === "IN_PROGRESS" ||
    value === "NEEDS_UPDATE"
  ) {
    return styles.badgeWarn;
  }
  return styles.badge;
}

function needStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    PROPOSED: "Đề xuất",
    TESTING: "Đang kiểm chứng",
    SUPPORTED: "Đã có hỗ trợ",
    REJECTED: "Đã bác bỏ",
    INSUFFICIENT_EVIDENCE: "Chưa đủ bằng chứng",
  };
  return labels[value] ?? value;
}

function reasonLabel(value: string): string {
  const labels: Record<string, string> = {
    no_content_or_selected_write_plan: "Chưa có nội dung hoặc kế hoạch viết được chọn.",
    selected_content_opportunity_exists: "Đã có ContentOpportunity được chọn.",
    content_work_exists_without_current_published_completion:
      "Đã có công việc nội dung nhưng chưa có bản xuất bản hiện hành.",
    published_content_exists: "Đã có nội dung đang được xuất bản.",
    selected_update_or_refresh_targets_published_content:
      "Có kế hoạch cập nhật/refresh nhắm tới nội dung đã xuất bản.",
    newer_unpublished_revision_exists:
      "Có revision mới hơn nhưng chưa được xuất bản.",
    unresolved_quality_failure_or_final_review_revision:
      "Còn lỗi chất lượng hoặc quyết định duyệt yêu cầu chỉnh sửa.",
    selected_update_target_ref_invalid:
      "Tham chiếu target cập nhật không hợp lệ hoặc không còn khớp.",
    additional_weak_content_does_not_erase_published_coverage:
      "Có nội dung yếu bổ sung nhưng không xóa trạng thái coverage đã xuất bản.",
    weak_or_failed_revision_exists:
      "Tồn tại revision yếu hoặc chưa qua chất lượng.",
    duplicate_candidate_detected:
      "Phát hiện ứng viên nội dung trùng theo cùng Need/locale/intent/question.",
  };
  return labels[value] ?? value;
}

function formatLocale(value: string): string {
  if (value === "vi-VN") return "Tiếng Việt";
  if (value === "en") return "Tiếng Anh";
  return value;
}

function ContentItemCard({
  item,
  stageLabels,
}: {
  item: ContentCoverage["needs"][number]["content_items"][number];
  stageLabels: Map<string, string>;
}) {
  return (
    <article className={styles.contentItem}>
      <div className={styles.sectionHeader}>
        <div>
          <p className="eyebrow">
            {formatLocale(item.locale)} · {item.need_role}
          </p>
          <h3>{item.primary_question}</h3>
        </div>
        <span className={styles.badge}>{item.item_status}</span>
      </div>
      <p>
        <strong>Intent:</strong> {item.primary_intent}
      </p>
      <p>
        <strong>Content role:</strong> {item.content_role}
      </p>
      <p className={styles.meta}>Key: {item.canonical_key}</p>
      <div className={styles.journeyChips}>
        {item.journey_stages.length === 0 ? (
          <span className={styles.badge}>Chưa gán journey stage</span>
        ) : (
          item.journey_stages.map((stage) => (
            <span className={styles.badge} key={stage.stage_key}>
              {stageLabels.get(stage.stage_key) ?? stage.stage_key}
            </span>
          ))
        )}
      </div>
      <dl className={styles.definition}>
        <dt>Version mới nhất</dt>
        <dd>
          {item.latest_version
            ? "v" + item.latest_version.version_no + " · " + item.latest_version.status
            : "Chưa có"}
        </dd>
        <dt>Version đã publish</dt>
        <dd>
          {item.latest_published_version
            ? "v" + item.latest_published_version.version_no + " · " + item.latest_published_version.status
            : "Chưa có"}
        </dd>
      </dl>
      {item.unresolved_negative_final_decision ? (
        <div className={styles.notice + " " + styles.stale}>
          Final review: {item.unresolved_negative_final_decision.decision}
          {item.unresolved_negative_final_decision.comment
            ? " — " + item.unresolved_negative_final_decision.comment
            : ""}
        </div>
      ) : null}
      {item.publication?.canonical_url ? (
        <p>
          <a
            href={item.publication.canonical_url}
            target="_blank"
            rel="noreferrer"
          >
            Mở URL đang xuất bản
          </a>
        </p>
      ) : null}
    </article>
  );
}

export default function ContentMapPage() {
  const [coverage, setCoverage] = useState<ContentCoverage | null>(null);
  const [filter, setFilter] = useState<CoverageStatus | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [staleMessage, setStaleMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      setLoading(true);
      setError("");
      try {
        const nextCoverage = await loadContentCoverage(PROJECT_SLUG);
        if (!cancelled) setCoverage(nextCoverage);
      } catch (nextError) {
        if (!cancelled) {
          setError(
            nextError instanceof Error
              ? nextError.message
              : "Không thể tải Content Coverage.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const stageLabels = useMemo(
    () =>
      new Map(
        (coverage?.journey.stages ?? []).map((stage) => [
          stage.key,
          stage.label,
        ]),
      ),
    [coverage],
  );

  const visibleNeeds = useMemo(() => {
    if (!coverage) return [];
    if (filter === "ALL") return coverage.needs;
    return coverage.needs.filter((lane) => lane.coverage_status === filter);
  }, [coverage, filter]);

  async function refresh() {
    setLoading(true);
    setError("");
    setStaleMessage("");
    try {
      setCoverage(await loadContentCoverage(PROJECT_SLUG));
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới Content Coverage.";
      if (coverage) {
        setStaleMessage(
          "Lần làm mới thất bại (" +
            message +
            "). Dữ liệu đang hiển thị là lần tải thành công gần nhất.",
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Content Coverage</p>
          <h1>Bản đồ nội dung</h1>
          <p className="intro">
            Xem mức coverage theo Need bằng trạng thái canonical. Không dùng điểm
            số tự chế và không đồng nhất “đã publish” với “đã giải quyết vấn đề
            khách hàng”.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refresh()}
            disabled={loading}
          >
            Làm mới
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        Coverage là trạng thái nội dung, không phải bằng chứng hiệu quả với khách
        hàng. Backend yêu cầu measurement riêng trước khi kết luận nội dung
        “working”.
      </div>

      {loading && !coverage ? (
        <div className={styles.loading} role="status">
          Đang tải Content Coverage…
        </div>
      ) : null}
      {error ? (
        <div className={styles.error} role="alert">
          Không thể đọc Content Coverage: {error}
        </div>
      ) : null}
      {staleMessage ? (
        <div className={styles.notice + " " + styles.stale} role="status">
          {staleMessage}
        </div>
      ) : null}

      {coverage ? (
        <>
          <section
            className={styles.coverageSummary}
            aria-label="Tổng quan trạng thái coverage"
          >
            {STATUS_ORDER.map((status) => (
              <div className={styles.coverageCount} key={status}>
                <span>{coverageLabel(status)}</span>
                <strong>{coverage.counts[status] ?? 0}</strong>
              </div>
            ))}
          </section>

          <div className={styles.filters} aria-label="Lọc trạng thái coverage">
            <button
              type="button"
              className={
                filter === "ALL"
                  ? styles.filterButtonActive
                  : styles.filterButton
              }
              onClick={() => setFilter("ALL")}
              aria-pressed={filter === "ALL"}
            >
              Tất cả
            </button>
            {STATUS_ORDER.map((status) => (
              <button
                type="button"
                key={status}
                className={
                  filter === status
                    ? styles.filterButtonActive
                    : styles.filterButton
                }
                onClick={() => setFilter(status)}
                aria-pressed={filter === status}
              >
                {coverageLabel(status)}
              </button>
            ))}
          </div>

          {visibleNeeds.length === 0 ? (
            <div className={styles.empty}>
              Không có Need nào trong bộ lọc hiện tại.
            </div>
          ) : (
            <section className={styles.coverageList}>
              {visibleNeeds.map((lane) => (
                <article className={styles.coverageLane} key={lane.need.id}>
                  <div className={styles.coverageLaneHeader}>
                    <div>
                      <p className="eyebrow">
                        Need · {lane.need.type} · {needStatusLabel(lane.need.status)}
                      </p>
                      <h2>{lane.need.statement}</h2>
                    </div>
                    <span className={coverageClass(lane.coverage_status)}>
                      {coverageLabel(lane.coverage_status)}
                    </span>
                  </div>

                  <ul className={styles.reasonList}>
                    {lane.reason_codes.map((reason) => (
                      <li key={reason}>{reasonLabel(reason)}</li>
                    ))}
                  </ul>

                  {lane.selected_opportunities.length > 0 ? (
                    <div className={styles.evidenceBlock}>
                      <strong>ContentOpportunity đã chọn</strong>
                      <div className={styles.cards}>
                        {lane.selected_opportunities.map((opportunity) => (
                          <div className={styles.card} key={opportunity.id}>
                            <p>
                              <strong>{formatLocale(opportunity.locale)}</strong>{" "}
                              · {opportunity.decision}
                            </p>
                            <p>{opportunity.question}</p>
                            <small className={styles.meta}>
                              Intent: {opportunity.intent}
                            </small>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className={styles.evidenceBlock}>
                    <strong>Nội dung hiện có</strong>
                    {lane.content_items.length === 0 ? (
                      <p>Chưa có ContentItem trong lane này.</p>
                    ) : (
                      <div className={styles.contentItems}>
                        {lane.content_items.map((item) => (
                          <ContentItemCard
                            key={item.id}
                            item={item}
                            stageLabels={stageLabels}
                          />
                        ))}
                      </div>
                    )}
                  </div>

                  {lane.duplicate_candidates.length > 0 ||
                  lane.invalid_update_target_refs.length > 0 ? (
                    <div className={styles.evidenceBlock}>
                      <strong>Điểm cần kiểm tra</strong>
                      {lane.duplicate_candidates.length > 0 ? (
                        <p>
                          Có {lane.duplicate_candidates.length} nhóm ứng viên
                          trùng được backend đánh dấu.
                        </p>
                      ) : null}
                      {lane.invalid_update_target_refs.length > 0 ? (
                        <div className={styles.signalList}>
                          {lane.invalid_update_target_refs.map((ref) => (
                            <span key={ref}>
                              Update target không hợp lệ · {ref}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              ))}
            </section>
          )}
        </>
      ) : null}
    </main>
  );
}
