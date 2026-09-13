# T05.21A — Content Production Board

## Mục tiêu

Bổ sung một board read-only cấp ContentCase cho vận hành sản xuất nội dung. Đây là UI sản xuất nội dung, không phải UI quản lý coding repo.

## Operating model đã khóa

- ContentCase/bài nội dung là thực thể chính.
- Codex là tác nhân điều phối chính.
- Codex có thể sinh/chọn subagent theo từng stage.
- Antigravity là worker/tool dưới quyền Codex, không phải peer ngang hàng.
- UI chính 100% tiếng Việt; tên sản phẩm và mã kỹ thuật chỉ xuất hiện khi cần.

## Scope T05.21A

- endpoint read-only `GET /journal/production-board`;
- nhóm bài theo: `Đang thực hiện`, `Chờ xử lý`, `Bị chặn`, `Chờ duyệt`, `Hoàn thành`;
- mỗi bài hiển thị: mã, nội dung, giai đoạn, ngôn ngữ, `Điều phối: Codex`, tác nhân hiện tại, cập nhật gần nhất, việc tiếp theo;
- execution drill-down dựa duy nhất trên persisted `ModelCall` / `ToolCall` telemetry;
- không bịa subagent hoặc Antigravity nếu runtime chưa persist chúng;
- route UI `/production` dành cho board;
- màn hình T05.20B tiếp tục là case-detail/review surface.

## Điều không làm trong slice này

- không thêm migration;
- không thêm orchestration runtime;
- không tạo schema subagent mới;
- không tự chạy Codex/Antigravity;
- không publish;
- không thay approval semantics;
- không biến board thành task manager cho coding repo.

## Quy tắc trạng thái

- persisted inconsistency hoặc quality FAIL → `Bị chặn`;
- chờ Founder review → `Chờ duyệt`;
- có run/step/model/tool đang chạy → `Đang thực hiện`;
- approved/published/rejected terminal state → `Hoàn thành`;
- còn lại → `Chờ xử lý`.

Semantic next-action phải thắng các historical source runs cũ. Ví dụ một ContentVersion đã approved không được hiển thị stage `outline` chỉ vì source run lịch sử còn `waiting_approval`.

## Telemetry honesty

Repo hiện persist `StepRun`, `ModelCall`, `ToolCall` nhưng chưa có entity chuẩn cho Codex delegation/subagent tree. Vì vậy:

- `coordinator = Codex` là operating policy đã được Founder xác nhận;
- current worker chỉ hiện khi có persisted running ModelCall/ToolCall;
- execution chain chỉ dùng persisted execution records;
- khi chưa có subagent/Antigravity telemetry, UI phải nói rõ chưa có dữ liệu thay vì suy đoán.

## Acceptance

- board API read-only, không đổi row counts;
- approved M1 nằm ở `Hoàn thành`, stage `Đã duyệt`;
- pending final review nằm ở `Chờ duyệt`, stage `Duyệt nội dung cuối`;
- Codex hiển thị là coordinator duy nhất;
- UI board bằng tiếng Việt;
- article review/quality/provenance/approval vẫn nằm trong T05.20B case detail;
- full CI xanh.
