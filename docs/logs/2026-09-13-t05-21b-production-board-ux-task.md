# T05.21B — Production Board UX refinement

## Mục tiêu

Hoàn thiện các UX gap đã được Agent Local chứng minh trên T05.21A mà không thay đổi read-model semantics, orchestration runtime hoặc persisted data.

## Bằng chứng đầu vào

T05.21A local proof trên M1:

- board/API read-only đúng persisted truth;
- M1 ở `Hoàn thành`, stage `Đã duyệt`;
- coordinator `Codex`;
- không bịa subagent/Antigravity;
- counts trước/sau không đổi;
- đánh giá `PARTIAL FIT` do ba UX gap.

## Scope

1. Bấm một ContentCase trên `/production` phải mở Review Console đúng case đó.
2. Review Console phải đọc `?case=<ContentCase UUID>` và ưu tiên đúng case khi ID hợp lệ; ID không tồn tại thì fallback an toàn về case đầu tiên.
3. Khi đổi case trong Review Console, URL phải được đồng bộ bằng `history.replaceState` để link có thể chia sẻ/tái mở.
4. Production board phải vừa viewport desktop thông thường tốt hơn; cột `Việc tiếp theo` không bị cắt ở viewport đã dùng trong local proof. Chỉ màn hình nhỏ mới cần scroll ngang.
5. Thu gọn hero/spacing để board xuất hiện sớm hơn và tránh lặp cảm giác landing page.
6. Execution chain phải dùng stage label có nghĩa từ persisted role/task key: góc tiếp cận, dàn ý, Writer VI/EN, review/revise, assertion audit, source-copy, cleanup, package/final review khi nhận diện được.
7. Codex vẫn là coordinator; subagent/Antigravity chỉ hiển thị khi persisted telemetry có thật.

## Không làm

- không migration;
- không schema delegation/subagent mới;
- không orchestration runtime;
- không model/provider/tool call;
- không publish/WordPress;
- không thay approval semantics;
- không biến board thành coding task manager.

## Acceptance

- `/production` load bình thường;
- click row mở `/?case=<exact ContentCase ID>`;
- Review Console hiển thị đúng case được yêu cầu;
- đổi case cập nhật query param mà không reload không cần thiết;
- desktop proof không còn cắt cột `Việc tiếp theo`;
- execution chain không còn toàn nhãn generic khi task key có thể phân loại;
- UI vận hành chính tiếp tục bằng tiếng Việt;
- backend persisted counts không đổi khi chỉ xem/chuyển trang;
- full CI xanh.

## Local proof sau merge candidate

Agent Local kiểm tra trên DB M1 thật:

- exact deep-link;
- viewport fit;
- stage-aware execution labels;
- read-only counts before/after;
- screenshot production board + case detail được mở từ board.
