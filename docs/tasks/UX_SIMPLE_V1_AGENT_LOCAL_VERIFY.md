# UX-SIMPLE-01 — Agent Local exact-SHA verification task

**Status:** PREPARED, NOT DISPATCHED; chỉ chạy sau khi MG hoàn tất các lát cắt UX-01A/B/C/D và Founder giao task này.
**Repo:** thiendzung/ContentEngine
**Branch:** release/content-production-v1-rc1
**SHA:** Founder/MG sẽ cung cấp exact candidate SHA ngay trước khi chạy; không dùng SHA trong tài liệu cũ.

## Mục tiêu

Xác minh người không chuyên có thể chọn nội dung đã chuẩn bị, theo dõi, duyệt đúng ba cổng biên tập và xem/xuất nhật ký an toàn. Không yêu cầu chạy content production thật hoặc model/research call cho gate UX.

## Quyền và giới hạn

- Chỉ đọc mã và chạy tests/smoke trên checkout exact SHA và database test an toàn.
- Không cho phép operational migration, reset DB vận hành, tác vụ model/research tốn phí, sửa code chưa được giao, auto-publish hoặc merge.
- Không dùng sleep/ps/pgrep hay vòng polling liên tục để kiểm tra trạng thái; dùng sự kiện, process exit và kiểm tra một lần khi cần.
- Không log hay commit credentials, raw prompt, user/customer/source sensitive content, dumps.

## Điều kiện đầu vào

1. Git remote đúng thiendzung/ContentEngine; worktree sạch; HEAD đúng SHA được chỉ định.
2. Đọc AGENTS.md, AI_context.MD, docs/PLAN.md, docs/TASKS.md, docs/CHECKLIST.md và docs/releases/UX_SIMPLE_OPERATOR_V1_PLAN.md.
3. Mọi code UX-01A-D phải có trên candidate. Nếu còn TODO quan trọng, trả INCOMPLETE_SCOPE thay vì PASS.

## Các gate

### A — Static / contract

- 3 tác vụ bình thường có thể thấy ngay: Viết bài, Bài đang làm, Cần tôi duyệt.
- Nhóm Nâng cao chứa các công cụ chuyên môn; link/URL cũ không bị phá.
- Manual 14-field intake vẫn giữ schema và preflight; không có tác vụ tự điền fake evidence/customer truth.
- Frontend không tự cấp quyền/cho phép action ngoài backend allowed_intents, route/admission hoặc human gate.
- Không thay đổi ContentCase, EvidenceSet, Approval, Quality, publish permissions, canonical API mutation hay idempotency.

### B — Static tests

- Frontend lint, typecheck, production build PASS.
- Focused UI/component tests hoặc regression tương đương cho navigation, chọn bài, approve và stale/reconcile PASS.
- Backend tests chỉ nếu có read-only log endpoint mới; tách DB test an toàn.

### C — Browser acceptance

Viewport 1440px, 1024px và 390px; bàn phím/tab/focus; kiểm tra:

- Mở UX entry -> thấy ba lựa chọn chính.
- Chọn một candidate hợp lệ qua Question Map; không phải nhập lại manual brief.
- Candidate thiếu eligibility -> hiển thị nguyên nhân và dừng; không tạo case/trạng thái giả.
- Bài queued/running/blocked/waiting Angle/Outline/final/complete đều có giải thích tiếng Việt và duy nhất hành động chính hợp lệ.
- Approve cho đúng bản đã review, không bỏ qua confirmation; VI/EN final approval độc lập nếu backend yêu cầu.
- Stale-state/ambiguous network error vẫn khóa hành động tới khi reconcile.
- Xem timeline của một bài; kiểm tra export support report được lược dữ liệu nhạy cảm.
- Không có auto-publish. Không có interval polling 2.5s trong UX mới.

### D — Evidence báo cáo

Trả:

GOAL
EXACT_SHA
WORKTREE
STATIC_TESTS
BROWSER_DESKTOP
BROWSER_MOBILE
KEYBOARD
CANONICAL_GATES
LOG_EXPORT_SECURITY
NO_PUBLICATION
CHECKS_NOT_RUN
ISSUES
STATUS: PASS_UX_SIMPLE_V1 / BLOCKED_UX_SIMPLE_V1
NEXT

Giữ PR Draft cho đến khi MG review evidence; Founder là người merge. **Không chấm CONTENT_PRODUCTION_READY từ UX verification.**
