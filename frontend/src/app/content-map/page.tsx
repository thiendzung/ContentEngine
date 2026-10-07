"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  type ContentCoverage,
  type CoverageStatus,
  loadContentCoverage,
} from "../../lib/api/customer-intelligence";
import {
  uiDecisionLabel,
  uiIntentLabel,
  uiPriorityLabel,
} from "../../lib/ui/vi/content";
import {
  customerJourneyStageLabel,
  customerNeedTypeLabel,
} from "../../lib/ui/vi/customer";
import {
  planningActorLabel,
  planningContentRoleLabel,
  planningCoverageLabel,
  planningCoverageReasonLabel,
  planningNeedRoleLabel,
} from "../../lib/ui/vi/planning";
import { uiStatusLabel } from "../../lib/ui/vi/status";
import styles from "../intelligence.module.css";

const PROJECT_SLUG = "motgu";
const COVERAGE_SCHEMA_VERSION = 1;
const STATUS_ORDER: CoverageStatus[] = [
  "MISSING",
  "PLANNED",
  "IN_PROGRESS",
  "PUBLISHED",
  "NEEDS_UPDATE",
  "WEAK",
  "INSUFFICIENT_DATA",
];

function assertCoverageContract(coverage: ContentCoverage) {
  if (coverage.schema_version !== COVERAGE_SCHEMA_VERSION) {
    throw new Error("content_coverage_schema_version_unsupported");
  }
  if (
    !coverage.semantics.published_does_not_mean_customer_problem_solved ||
    !coverage.semantics.working_status_requires_measurement ||
    !coverage.semantics.same_need_does_not_imply_duplicate_content
  ) {
    throw new Error("content_coverage_semantics_contract_changed");
  }
  const countedNeeds = STATUS_ORDER.reduce(
    (total, status) => total + (coverage.counts[status] ?? 0),
    0,
  );
  if (countedNeeds !== coverage.needs.length) {
    throw new Error("content_coverage_count_mismatch");
  }
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
            {formatLocale(item.locale)} · {planningNeedRoleLabel(item.need_role)}
          </p>
          <h3>{item.primary_question}</h3>
        </div>
        <span className={styles.badge}>{uiStatusLabel(item.item_status)}</span>
      </div>
      <p>
        <strong>Ý định:</strong> {uiIntentLabel(item.primary_intent)}
      </p>
      <p>
        <strong>Vai trò nội dung:</strong> {planningContentRoleLabel(item.content_role)}
      </p>
      <p className={styles.meta}>Khóa chuẩn: {item.canonical_key}</p>
      <div className={styles.journeyChips}>
        {item.journey_stages.length === 0 ? (
          <span className={styles.badge}>Chưa gán giai đoạn hành trình</span>
        ) : (
          item.journey_stages.map((stage) => (
            <span
              className={styles.badge}
              key={stage.stage_key}
              title={stage.reason}
            >
              {customerJourneyStageLabel(
                stage.stage_key,
                stageLabels.get(stage.stage_key) ?? stage.stage_key,
              )}
              {" · "}
              {planningActorLabel(stage.linked_by)}
            </span>
          ))
        )}
      </div>
      <dl className={styles.definition}>
        <dt>Phiên bản mới nhất</dt>
        <dd>
          {item.latest_version
            ? "v" + item.latest_version.version_no + " · " + uiStatusLabel(item.latest_version.status)
            : "Chưa có"}
        </dd>
        <dt>Phiên bản đã xuất bản</dt>
        <dd>
          {item.latest_published_version
            ? "v" + item.latest_published_version.version_no + " · " + uiStatusLabel(item.latest_published_version.status)
            : "Chưa có"}
        </dd>
      </dl>
      {item.unresolved_negative_final_decision ? (
        <div className={styles.notice + " " + styles.stale}>
          Duyệt cuối: {uiStatusLabel(item.unresolved_negative_final_decision.decision)}
          {item.unresolved_negative_final_decision.comment
            ? " — " + item.unresolved_negative_final_decision.comment
            : ""}
        </div>
      ) : null}
      {item.publication ? (
        <div className={styles.evidenceBlock}>
          <strong>Xuất bản</strong>
          <p>
            {item.publication.target} · {uiStatusLabel(item.publication.external_status)}
          </p>
          <p className={styles.meta}>
            Phiên bản nội dung: {item.publication.current_content_version_id}
          </p>
          {item.publication.canonical_url ? (
            <p>
              <a
                href={item.publication.canonical_url}
                target="_blank"
                rel="noreferrer"
              >
                Mở URL chuẩn
              </a>
            </p>
          ) : (
            <p className={styles.meta}>Chưa có URL chuẩn.</p>
          )}
        </div>
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
        assertCoverageContract(nextCoverage);
        if (!cancelled) setCoverage(nextCoverage);
      } catch (nextError) {
        if (!cancelled) {
          setError(
            nextError instanceof Error
              ? nextError.message
              : "Không thể tải độ phủ nội dung.",
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
          customerJourneyStageLabel(stage.key, stage.label),
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
      const nextCoverage = await loadContentCoverage(PROJECT_SLUG);
      assertCoverageContract(nextCoverage);
      setCoverage(nextCoverage);
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "Không thể làm mới độ phủ nội dung.";
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
    <main className={styles.page} aria-busy={loading}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ContentEngine · Độ phủ nội dung</p>
          <h1>Bản đồ nội dung</h1>
          <p className="intro">
            Xem mức độ phủ theo nhu cầu bằng trạng thái chuẩn. Không dùng điểm
            số tự chế và không đồng nhất “đã xuất bản” với “đã giải quyết vấn đề
            khách hàng”.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link
            className={styles.buttonSecondary}
            href="/content-map/question-map"
          >
            Bản đồ câu hỏi
          </Link>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? "Đang làm mới…" : "Làm mới"}
          </button>
        </div>
      </header>

      <div className={styles.notice}>
        <strong>Giới hạn quy ước:</strong> huy hiệu độ phủ là trạng thái ở cấp
        nhu cầu trong phạm vi dữ liệu hiện tại. Ngôn ngữ và hành trình bên dưới chỉ là liên kết
        chuẩn của từng nội dung; giao diện không tạo trạng thái ô
        Nhu cầu × Hành trình × ngôn ngữ. “Đã xuất bản” cũng không có nghĩa vấn đề khách hàng
        đã được giải quyết; trạng thái đang hoạt động vẫn cần đo lường riêng, và cùng nhu cầu
        không tự động được coi là trùng lặp.
      </div>

      {loading && !coverage ? (
        <div
          className={styles.loading}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          Đang tải độ phủ nội dung…
        </div>
      ) : null}
      {error ? (
        <div className={styles.error} role="alert" aria-atomic="true">
          Không thể đọc độ phủ nội dung: {error}
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

      {coverage ? (
        <>
          <section
            className={styles.coverageSummary}
            aria-label="Tổng quan trạng thái độ phủ"
          >
            {STATUS_ORDER.map((status) => (
              <div className={styles.coverageCount} key={status}>
                <span>{planningCoverageLabel(status)}</span>
                <strong>{coverage.counts[status] ?? 0}</strong>
              </div>
            ))}
          </section>

          <div
            className={styles.filters}
            role="group"
            aria-label="Lọc trạng thái độ phủ"
          >
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
                {planningCoverageLabel(status)}
              </button>
            ))}
          </div>

          {visibleNeeds.length === 0 ? (
            <div className={styles.empty} role="status">
              Không có nhu cầu nào trong bộ lọc hiện tại.
            </div>
          ) : (
            <section className={styles.coverageList}>
              {visibleNeeds.map((lane) => (
                <article className={styles.coverageLane} key={lane.need.id}>
                  <div className={styles.coverageLaneHeader}>
                    <div>
                      <p className="eyebrow">
                        Độ phủ theo nhu cầu · {customerNeedTypeLabel(lane.need.type)} ·{" "}
                        {uiStatusLabel(lane.need.status)}
                      </p>
                      <h2>{lane.need.statement}</h2>
                    </div>
                    <span className={coverageClass(lane.coverage_status)}>
                      {planningCoverageLabel(lane.coverage_status)}
                    </span>
                  </div>

                  <ul className={styles.reasonList}>
                    {lane.reason_codes.map((reason) => (
                      <li key={reason}>{planningCoverageReasonLabel(reason)}</li>
                    ))}
                  </ul>

                  {lane.selected_opportunities.length > 0 ? (
                    <div className={styles.evidenceBlock}>
                      <strong>Cơ hội nội dung đã chọn</strong>
                      <div className={styles.cards}>
                        {lane.selected_opportunities.map((opportunity) => (
                          <div className={styles.card} key={opportunity.id}>
                            <p>
                              <strong>{formatLocale(opportunity.locale)}</strong>{" "}
                              · {uiDecisionLabel(opportunity.decision)} · {uiPriorityLabel(opportunity.priority)}
                            </p>
                            <p>{opportunity.question}</p>
                            <p className={styles.meta}>
                              Ý định: {uiIntentLabel(opportunity.intent)}
                            </p>
                            {opportunity.existing_content_refs.length > 0 ? (
                              <div className={styles.signalList}>
                                {opportunity.existing_content_refs.map((ref) => (
                                  <span key={ref}>
                                    Đích hiện có · {ref}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            {opportunity.selection_refs.length > 0 ? (
                              <div className={styles.evidenceBlock}>
                                <strong>Lựa chọn của người dùng</strong>
                                <ul>
                                  {opportunity.selection_refs.map((selection) => (
                                    <li key={selection.id}>
                                      {planningActorLabel(selection.selected_by)} · {selection.reason}
                                      <span className={styles.meta}>
                                        {" "}
                                        ({selection.selected_at})
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className={styles.evidenceBlock}>
                    <strong>Nội dung hiện có</strong>
                    {lane.content_items.length === 0 ? (
                      <p role="status">Chưa có nội dung trong nhóm này.</p>
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
                        <div className={styles.cards}>
                          {lane.duplicate_candidates.map((duplicate) => (
                            <div
                              className={styles.card}
                              key={
                                duplicate.locale +
                                ":" +
                                duplicate.primary_intent +
                                ":" +
                                duplicate.normalized_primary_question
                              }
                            >
                              <p>
                                <strong>Ứng viên trùng lặp</strong> ·{" "}
                                {formatLocale(duplicate.locale)}
                              </p>
                              <p>
                                Ý định: {uiIntentLabel(duplicate.primary_intent)}
                              </p>
                              <p>
                                Câu hỏi chuẩn hóa:{" "}
                                {duplicate.normalized_primary_question}
                              </p>
                              <div className={styles.signalList}>
                                {duplicate.content_item_ids.map((id) => (
                                  <span key={id}>Nội dung · {id}</span>
                                ))}
                              </div>
                              <small className={styles.meta}>
                                Lý do: {planningCoverageReasonLabel(duplicate.reason)}
                              </small>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {lane.invalid_update_target_refs.length > 0 ? (
                        <div className={styles.signalList}>
                          {lane.invalid_update_target_refs.map((ref) => (
                            <span key={ref}>
                              Đích cập nhật không hợp lệ · {ref}
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