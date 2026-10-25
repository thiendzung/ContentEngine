# UX-SIMPLE-01 — Kế hoạch ContentEngine UX-first v1.0.0

Date: 2026-10-25
Issue: #417
PR: #418 (Draft)
Status: PLANNED — không phải UX PASS hoặc CONTENT READY.

## Founder decision

Hoàn thiện và kiểm thử UX vận hành trước; sau đó Founder trực tiếp sản xuất một bài thật, xuất báo cáo log an toàn, MG đọc dữ liệu và chỉ tối ưu lỗi có bằng chứng.

Không phát triển provider, research/SEO engine, auto-publishing hoặc CMS mới trong scope này.

## Mục tiêu một người mới sử dụng

1. Chọn một bài đã có trong kế hoạch; không cần điền lại toàn bộ manual intake.
2. Thấy bài đang ở giai đoạn nào, vì sao bị chặn và bước tiếp theo hợp lệ.
3. Duyệt Góc viết → Dàn ý → Bài cuối theo backend; lưu ý duyệt cuối có thể riêng cho từng locale.
4. Nhận package để kiểm tra trước đăng và đăng WordPress thủ công.
5. Xem hoặc xuất nhật ký một bài dạng dễ hiểu, không tiết lộ dữ liệu nhạy cảm.

## Nguyên tắc giao diện

- Ba lối chính: Viết bài / Bài đang làm / Cần tôi duyệt.
- Các phần Khách hàng, Bản đồ nội dung, Học từ dữ liệu, Hệ thống, Nhật ký chung, form yêu cầu riêng đặt dưới Nâng cao.
- Mỗi màn hình chỉ ưu tiên một việc cần làm theo backend; ID/hash/model/usage và QA nâng cao nằm trong phần Chi tiết.
- Không tự suy diễn trạng thái/next action hoặc tự điền customer truth, evidence, originality hay approval.

## LEGO UX — thứ tự triển khai

### UX-01A — Trang bắt đầu và menu

- Tiếp tục đơn giản hóa trang /operator đã có trong #418.
- Gộp menu hiện đang lộ 7 mục thành 3 mục cơ bản + nhóm Nâng cao.
- Giữ nguyên tất cả đường dẫn cũ và quyền hiện có.
- Pass khi người mới nhận ra ngay nơi bắt đầu, xem tiến độ và xem việc chờ duyệt.

### UX-01B — Chọn bài, không bắt người dùng làm quản trị

- Dùng lại Question Map / ContentOpportunity / production route / admission có sẵn.
- Trang chọn bài cho thấy: Câu hỏi, Người đọc, Giá trị, Trạng thái, Việc nên làm.
- Tên kỹ thuật CREATE/UPDATE/REFRESH/MERGE được giải thích bằng tiếng Việt; API mutation không đổi.
- Chỉ hiển thị thông tin còn thiếu mà backend xác định được; dữ liệu thiếu phải dừng an toàn, không tự điền giả.
- Form manual 14 trường giữ ở Nâng cao dành cho biên tập viên.
- Pass UX khi người dùng phân biệt rõ ứng viên có thể tiếp tục / bị chặn, hiểu lý do và hành động tiếp theo; UI không cho thực hiện hành động bị khóa. Canonical handoff/backend integration được nghiệm thu ở gate riêng.

### UX-01C — Bàn làm việc một bài, một hành động

- Hiện trạng thái, lý do và một hành động chính được backend cho phép.
- Hướng dẫn rõ ở Angle / Outline / Final; giữ exact artifact/version/hash, stale-state protection, idempotency và xác nhận của Founder.
- Đưa đầu vào, cảnh báo phụ, quality chi tiết và mã kỹ thuật vào các mục mở rộng.
- Loại interval kiểm tra trạng thái mỗi 2.5 giây. Cập nhật sau mutation, khi tab/window lấy lại focus, và nút Tải lại; chỉ thêm SSE/WebSocket khi có cơ chế đáng tin cậy, không hứa live update.
- Browser proof dùng deterministic UI fixture / mocked API để kiểm tra state matrix tối thiểu: READY, QUEUED, RUNNING, BLOCKED, AWAITING_APPROVAL, COMPLETE, ERROR, STALE và EMPTY.
- Với mỗi state phải thấy rõ: trạng thái hiện tại, lý do, một primary action (nếu có), secondary details không lấn át, manual refresh, focus/visibility refresh và keyboard focus.
- Pass UX khi các state trên có lời giải thích dễ hiểu và hành động đúng theo contract hiển thị; không yêu cầu backend thật tạo được mọi state để đóng UX gate.

### UX-01D — Nhật ký một bài & xuất báo cáo

- Reuse ContentRun, StepRun, Job, ModelCall, ToolCall, QualityEvaluation, Approval, Artifact đang lưu.
- Daily Digest là nhật ký thay đổi toàn hệ thống, không phải toàn bộ trace của một bài.
- Nếu endpoint hiện tại thiếu, chỉ thêm một read-only projection theo ContentCase; không thêm database bảng log mới hoặc scheduler.
- Hiện timeline: thời gian, bước, kết quả, lý do lỗi, retry, QA và next action nếu có căn cứ.
- Xuất báo cáo JSON/Markdown an toàn chỉ từ allowlist: case/run/step IDs, timestamp, stage/status/attempt/duration/error class, refs/hashes, known usage/cost, QA result.
- Không đưa vào bản xuất: raw prompt, source/private content, token/API key, .env, cookies, PII, chain-of-thought hay DB dumps. Nếu redaction chưa chứng minh, chặn xuất.
- Người dùng chủ động chia sẻ báo cáo; không auto-upload lên GitHub hay gửi cho MG.

### UX-01E — Kiểm thử trước khi Founder chạy thật

- Exact SHA + worktree sạch; frontend lint/typecheck/build + test liên quan.
- Browser ở 1440/1024/390/320 px, bàn phím/focus, luồng thông thường và lỗi; 320 px dùng để kiểm reflow, không mất thông tin/chức năng.
- Dùng deterministic UI fixtures / mocked API để render và thao tác toàn bộ state matrix; không gọi model, không ghi operational DB và không yêu cầu canonical handoff thật chỉ để kiểm thử UI.
- Mock phải bám đúng API/view contract hiện tại; test UI không được tự chế thêm trạng thái authority mà backend không định nghĩa.
- Kiểm tra số click/hành động cần cho trường hợp có dữ liệu chuẩn, tình huống thiếu dữ liệu, lỗi stale/reconcile, focus/visibility refresh và manual refresh.
- Backend integration smoke được nghiệm thu riêng sau UX gate; một lỗi API/receipt/fixture backend không làm UX FAIL nếu state UI tương ứng đã được mock đúng contract và browser proof đạt.
- Agent Local trả kết quả, MG review + bổ sung test; Founder là người merge.
- Gate này là PASS_UX_SIMPLE_V1, chưa đồng nghĩa CONTENT_PRODUCTION_READY.

## Các gate nghiệm thu tách biệt

1. UX_UI_READY: UI dễ hiểu, mocked-state browser proof đạt trên exact SHA, responsive/keyboard/focus đạt. Có thể merge/trình bày giao diện mà chưa yêu cầu backend thật materialize case hoặc một bài thật đến Angle.
2. BACKEND_INTEGRATION_READY: API/DB/handoff canonical hoạt động với fixture/test data được ủy quyền. Blocker như HTTP 409, receipt thiếu hoặc fixture backend được ghi riêng ở gate này, không làm UX_UI_READY fail.
3. CONTENT RUNTIME: Sau khi UX và integration đủ sẵn sàng, Founder vận hành một case thật (ưu tiên Q07). Chỉ ghi PASS_CONTENT_PRODUCTION_V1_RC1 khi case đạt đúng phạm vi/đủ bằng chứng; nếu dừng ở evidence thì ghi BLOCKED và giữ nguyên bằng chứng.

Merge code không tự cho phép model call, migration, publication hay override approval.

## Vòng tối ưu dựa trên log

Founder chạy 1 bài → Xuất báo cáo đã lọc → MG chia thành bug / cấu hình / evidence thiếu / UX / chất lượng nội dung → chọn lỗi có bằng chứng và một sửa nhỏ → test hồi quy → Founder duyệt merge → đo lại.

Metric dùng được: thao tác thủ công, thời gian đến gate, blocker theo stage, retry, duration, QA failures, số lần Founder cần sửa, cost/tokens chỉ khi được đo thực. Không đặt KPI token/click ảo.

Ưu tiên sửa: bảo mật/toàn vẹn dữ liệu > thông tin sai > workflow lỗi > cản trở người dùng > UX khó hiểu > thẩm mỹ.

## Phân loại blocker

- UX_BLOCKER: layout/reflow, nhãn khó hiểu, hierarchy sai, keyboard/focus, state rendering, primary action, refresh UX hoặc thao tác quản lý.
- INTEGRATION_BLOCKER: API 4xx/5xx, receipt/fixture thiếu, canonical handoff, database/pipeline/test-data contract.
- CONTENT_RUNTIME_BLOCKER: evidence/model/provider/quality/publishing trên case thật.
- Không sửa backend chỉ để làm cho browser UX proof đi qua; dùng mocked API bám đúng contract cho gate UX.

## Giới hạn

- Không đổi backend workflow authority, EvidenceSet/QA gates, ba human approval gates, status/allowed_intents hoặc publish permissions.
- Không có tự động WordPress publish.
- Không chạy test destructive trên operational database, không đổi .env hay migration chỉ vì UI.
- Không polling liên tục bằng sleep/ps/pgrep hoặc setInterval trong luồng UX mới.
- Một implementation WIP và một Agent Local verification; không mở PR cho mỗi thay đổi nhỏ.

## Điều kiện kết thúc công việc UI trước vận hành

- 3 lối chính dễ tìm;
- một bài có sẵn đi qua đúng đường chọn, không nhập lại 14 trường thủ công;
- mọi trạng thái đều có câu giải thích và next action;
- log có cách xem/chia sẻ an toàn;
- browser smoke/lint/typecheck/build đạt exact SHA.

Sau Gate UX, ngừng cải tiến dựa trên cảm giác. Mọi nâng cấp tiếp theo phải từ báo cáo và lỗi thực tế.
