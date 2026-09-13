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

## Local proof — candidate đầu

Agent Local verified trên DB M1 thật, head `af9844c3ee509d6f92defb1fad6bf6801107272c`:

- exact deep-link từ board sang `/?case=f0bfbad7-c266-4de1-8fd4-a85ad206e6ce` PASS;
- viewport `1235px`: `clientWidth == scrollWidth == 1177px`, đủ 8 cột, không scroll ngang;
- board/state/coordinator/read-only invariants PASS;
- 8 persisted ModelCalls, 0 ToolCalls; không bịa subagent/Antigravity;
- counts trước/sau không đổi;
- đánh giá `PARTIAL FIT` do hai UX nhỏ: loading banner còn xuất hiện cùng detail và một `review_revise_en` còn rơi về nhãn generic.

Agent Local cũng báo task doc không tồn tại, nhưng GitHub branch đã xác nhận file này tồn tại ở đúng path; đây không phải repo blocker.

## Final fixes sau local proof

- Review Console ẩn transient loading banner ngay khi `.case-overview` đã render, tránh hiển thị `Đang tải trạng thái nội dung…` đồng thời với dữ liệu đầy đủ.
- Execution chain ưu tiên persisted `technical_name` / task key để phân loại stage; `review_revise_en` phải hiển thị `Rà soát tiếng Anh` thay vì `Tác vụ nội dung`.

## Final CI

Final head: `7b617015d35e866ddbbae7150d47f62615c8cd5f`.

CI #648 PASS toàn bộ: backend lint/types/migration/tests, OpenAPI, frontend type generation/lint/typecheck/build.

## Final merge gate

Agent Local rerun ngắn chỉ cần xác nhận hai UX fix trên cùng M1 runtime. Không cần lặp lại toàn bộ read-only proof nếu counts/runtime unchanged.
