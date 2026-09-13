# T05.21 UI FIT CHECK — Agent Local

## Mục tiêu

Xác minh UI vận hành ContentEngine có phù hợp với mô hình điều phối sản xuất nội dung mới của Founder hay không. Đây là bước đánh giá, **không sửa code**.

## Mô hình vận hành phải phản ánh

1. **Codex là tác nhân điều phối chính** của toàn bộ quá trình sản xuất nội dung.
2. Với mỗi task/nhiệm vụ, Codex tự chọn hoặc sinh các **subagent chuyên trách** phù hợp: nghiên cứu, lập dàn ý, viết, kiểm tra, sửa, kiểm chứng, v.v.
3. **Antigravity là worker/tool dưới quyền điều phối của Codex**, không phải một tác nhân ngang hàng tự điều phối độc lập.
4. Thực thể chính trên UI phải là **bài/case nội dung và giai đoạn công việc**, không phải danh sách agent.
5. Founder cần nhìn nhanh được: bài nào đang ở đâu, việc gì đang chạy, ai/worker nào đang thực thi dưới Codex, bài nào bị chặn, bài nào chờ Founder duyệt, việc tiếp theo là gì.
6. Chi tiết subagent/worker nên drill-down khi cần; màn hình chính không được biến thành bảng kỹ thuật hoặc bảng quản lý coding repo.
7. UI vận hành chính bằng tiếng Việt. Nội dung bài tiếng Anh và mã kỹ thuật trong phần chi tiết có thể giữ nguyên.

## Board mục tiêu sơ bộ

Các trạng thái cấp cao nên gần với:

- Đang thực hiện
- Chờ xử lý
- Bị chặn
- Chờ duyệt
- Hoàn thành

Mỗi hàng/card đại diện cho một bài/case nội dung, có thể hiển thị tối thiểu:

- Nội dung / câu hỏi cơ hội
- Giai đoạn hiện tại
- Trạng thái
- Ngôn ngữ
- Điều phối: Codex
- Worker/subagent đang thực thi (nếu có)
- Cập nhật gần nhất
- Việc tiếp theo

Ví dụ drill-down thực thi:

`Codex → subagent nghiên cứu → subagent viết EN → Antigravity (browser/tool) → kiểm tra chất lượng`

Không trình bày `Codex`, `Antigravity`, subagent như các thành viên ngang hàng ở màn hình chính.

## Việc Agent Local cần làm

1. Sync đúng head hiện tại của branch `t05-20b-review-actions` và xác nhận SHA.
2. Chạy backend/frontend local như T05.20A.
3. Quan sát UI hiện tại và đối chiếu với mô hình trên.
4. **Không bấm các action ghi dữ liệu** nếu không có fixture riêng; ưu tiên read-only review.
5. Không sửa code, không migration, không model/research run.

## Phản hồi bắt buộc

Trả lời ngắn gọn theo mẫu:

```text
STATUS: FIT | PARTIAL FIT | NOT FIT

HEAD:
<sha>

ĐIỂM ĐÚNG:
- ...

ĐIỂM CHƯA ĐÚNG / DỄ HIỂU SAI:
- ...

ĐỀ XUẤT UI T05.21 (tối đa 5 mục, ưu tiên tối thiểu cần thiết):
1. ...
2. ...

KẾT LUẬN:
Một câu: UI nên tổ chức quanh <thực thể nào> và Codex/subagent/Antigravity nên xuất hiện như thế nào.
```

Nếu có thể, kèm 1–3 screenshot vùng UI liên quan để MG đối chiếu.