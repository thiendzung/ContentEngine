"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  createFounderJournalIntake,
  type JournalEditorialRole,
} from "../../lib/operator/journal-api";
import {
  clearIdempotencyKey,
  getOrCreateIdempotencyKey,
} from "../../lib/operator/idempotency";

const INTAKE_KEY = "journal-intake-pending";

type Props = {
  preflightReady: boolean;
};

type SourceLocale = "" | "vi-VN" | "en";
type ContentRole = "" | JournalEditorialRole;

type FormState = {
  source_locale: SourceLocale;
  research_country: string;
  required_vi: boolean;
  required_en: boolean;
  content_role: ContentRole;
  reader: string;
  situation: string;
  need: string;
  question: string;
  intent: string;
  promise: string;
  coverage_requirements: string;
  selection_reason: string;
  originality_material: string;
  originality_writer_use: string;
  originality_guardrails: string;
};

const initialState: FormState = {
  source_locale: "",
  research_country: "vn",
  required_vi: true,
  required_en: true,
  content_role: "",
  reader: "",
  situation: "",
  need: "",
  question: "",
  intent: "learn",
  promise: "",
  coverage_requirements: "",
  selection_reason: "",
  originality_material: "",
  originality_writer_use: "",
  originality_guardrails: "",
};

export function JournalIntakeForm({ preflightReady }: Props) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(initialState);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const requiredLocales = useMemo(() => {
    const values: string[] = [];
    if (form.required_vi) values.push("vi-VN");
    if (form.required_en) values.push("en");
    return values;
  }, [form.required_en, form.required_vi]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    clearIdempotencyKey(INTAKE_KEY);
    setForm((current) => ({ ...current, [key]: value }));
    setError("");
  }

  function setSourceLocale(locale: "vi-VN" | "en") {
    clearIdempotencyKey(INTAKE_KEY);
    setForm((current) => ({
      ...current,
      source_locale: locale,
      required_vi: locale === "vi-VN" ? true : current.required_vi,
      required_en: locale === "en" ? true : current.required_en,
    }));
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preflightReady || submitting) return;
    if (!form.source_locale) {
      setError("Cần chọn ngôn ngữ nguồn trước khi tạo Journal.");
      return;
    }
    const contentRole = form.content_role;
    if (!contentRole) {
      setError("Cần chọn rõ Journal này là Pillar hay Cluster.");
      return;
    }
    if (!requiredLocales.includes(form.source_locale)) {
      setError("Ngôn ngữ nguồn phải nằm trong các ngôn ngữ bắt buộc.");
      return;
    }
    const coverageRequirements = form.coverage_requirements
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (coverageRequirements.length === 0) {
      setError("Cần khai báo ít nhất một cam kết phạm vi, mỗi dòng một mục.");
      return;
    }
    if (coverageRequirements.length > 12) {
      setError("Tối đa 12 cam kết phạm vi cho một Journal.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await createFounderJournalIntake({
        project_slug: "motgu",
        source_locale: form.source_locale,
        research_country: form.research_country.trim(),
        required_locales: requiredLocales,
        content_role: contentRole,
        reader: form.reader.trim(),
        situation: form.situation.trim(),
        need: form.need.trim(),
        question: form.question.trim(),
        intent: form.intent.trim(),
        promise: form.promise.trim(),
        coverage_requirements: coverageRequirements,
        selection_reason: form.selection_reason.trim(),
        originality_material: form.originality_material.trim(),
        originality_writer_use: form.originality_writer_use.trim(),
        originality_guardrails: form.originality_guardrails.trim(),
        idempotency_key: getOrCreateIdempotencyKey(INTAKE_KEY),
      });
      clearIdempotencyKey(INTAKE_KEY);
      router.push(`/operator/journal/${encodeURIComponent(result.content_case_id)}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Không thể tạo Journal từ thông tin hiện tại.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="operator-panel intake-form" onSubmit={(event) => void submit(event)}>
      <div className="operator-panel-heading">
        <div>
          <p className="eyebrow">Founder intake</p>
          <h2>Tạo Journal mới</h2>
        </div>
        <span className="operator-note">Thông tin biên tập, không phải bằng chứng thị trường.</span>
      </div>

      <fieldset className="form-section">
        <legend>Phạm vi</legend>
        <div className="form-grid two">
          <label>
            <span>Ngôn ngữ nguồn</span>
            <select
              onChange={(event) => setSourceLocale(event.target.value as "vi-VN" | "en")}
              required
              value={form.source_locale}
            >
              <option disabled value="">Chọn ngôn ngữ nguồn</option>
              <option value="vi-VN">Tiếng Việt</option>
              <option value="en">Tiếng Anh</option>
            </select>
          </label>
          <label>
            <span>Vai trò nội dung</span>
            <select
              onChange={(event) => update("content_role", event.target.value as ContentRole)}
              required
              value={form.content_role}
            >
              <option disabled value="">Chọn Pillar hoặc Cluster</option>
              <option value="pillar">Pillar — bức tranh lớn</option>
              <option value="cluster">Cluster — vấn đề hẹp, đi sâu</option>
            </select>
            <small>
              Pillar tổng hợp và dẫn sang bài sâu; Cluster giải quyết một vấn đề hẹp hơn.
            </small>
          </label>
          <label>
            <span>Quốc gia nghiên cứu</span>
            <input
              maxLength={8}
              onChange={(event) => update("research_country", event.target.value)}
              required
              value={form.research_country}
            />
          </label>
          <div className="checkbox-field">
            <span>Ngôn ngữ bắt buộc</span>
            <label>
              <input
                checked={form.required_vi}
                disabled={form.source_locale === "vi-VN"}
                onChange={(event) => update("required_vi", event.target.checked)}
                type="checkbox"
              />
              VI
            </label>
            <label>
              <input
                checked={form.required_en}
                disabled={form.source_locale === "en"}
                onChange={(event) => update("required_en", event.target.checked)}
                type="checkbox"
              />
              EN
            </label>
          </div>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Nhu cầu nội dung</legend>
        <div className="form-grid two">
          <label>
            <span>Độc giả</span>
            <textarea
              onChange={(event) => update("reader", event.target.value)}
              required
              rows={3}
              value={form.reader}
            />
          </label>
          <label>
            <span>Tình huống</span>
            <textarea
              onChange={(event) => update("situation", event.target.value)}
              required
              rows={3}
              value={form.situation}
            />
          </label>
          <label>
            <span>Nhu cầu</span>
            <textarea
              onChange={(event) => update("need", event.target.value)}
              required
              rows={3}
              value={form.need}
            />
          </label>
          <label>
            <span>Lời hứa nội dung</span>
            <textarea
              onChange={(event) => update("promise", event.target.value)}
              required
              rows={3}
              value={form.promise}
            />
          </label>
          <label>
            <span>Cam kết phạm vi bắt buộc</span>
            <textarea
              onChange={(event) => update("coverage_requirements", event.target.value)}
              placeholder={"Mỗi dòng một mục, ví dụ:\nTreo và ánh sáng\nVệ sinh an toàn\nVận chuyển"}
              required
              rows={5}
              value={form.coverage_requirements}
            />
            <small>
              Angle phải nói rõ mục nào được giữ hoặc thu hẹp; Outline không được tự làm rơi
              mục đã giữ.
            </small>
          </label>
        </div>
        <label className="full-field">
          <span>Câu hỏi trung tâm</span>
          <textarea
            onChange={(event) => update("question", event.target.value)}
            required
            rows={3}
            value={form.question}
          />
        </label>
        <div className="form-grid two compact-grid">
          <label>
            <span>Ý định</span>
            <input
              maxLength={64}
              onChange={(event) => update("intent", event.target.value)}
              required
              value={form.intent}
            />
          </label>
          <label>
            <span>Lý do chọn làm Journal</span>
            <input
              onChange={(event) => update("selection_reason", event.target.value)}
              required
              value={form.selection_reason}
            />
          </label>
        </div>
      </fieldset>

      <fieldset className="form-section">
        <legend>Tư liệu MOTGU</legend>
        <label className="full-field">
          <span>Tư liệu gốc</span>
          <textarea
            onChange={(event) => update("originality_material", event.target.value)}
            required
            rows={4}
            value={form.originality_material}
          />
        </label>
        <div className="form-grid two">
          <label>
            <span>Cách người viết được phép sử dụng</span>
            <textarea
              onChange={(event) => update("originality_writer_use", event.target.value)}
              required
              rows={3}
              value={form.originality_writer_use}
            />
          </label>
          <label>
            <span>Giới hạn / guardrails</span>
            <textarea
              onChange={(event) => update("originality_guardrails", event.target.value)}
              required
              rows={3}
              value={form.originality_guardrails}
            />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">{error}</p>}
      {!preflightReady && (
        <p className="operator-block-note">
          Chưa thể tạo Journal mới vì preflight chưa READY.
        </p>
      )}
      <div className="form-actions">
        <button
          className="operator-button primary"
          disabled={!preflightReady || submitting}
          type="submit"
        >
          {submitting ? "Đang tạo…" : "Tạo Journal"}
        </button>
      </div>
    </form>
  );
}