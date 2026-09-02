# ContentEngine

ContentEngine là hệ thống sản xuất và học từ nội dung cho MOTGU.

Mục tiêu đầu tiên: tạo **Journal** và **Artwork content** chất lượng cao để xuất bản lên WordPress MOTGU, bằng tiếng Việt hoặc tiếng Anh theo cấu hình.

ContentEngine không được tối ưu cho số lượng bài. Hệ thống phải tối ưu đồng thời cho:

- giá trị thật với người đọc;
- độ đúng và khả năng truy nguyên nguồn;
- giọng thương hiệu MOTGU;
- khả năng được Search và hệ thống AI hiểu;
- khả năng dẫn người phù hợp sang Artist, Artwork, Visit, Workshop hoặc Inquiry;
- khả năng đo, học và cải thiện sau mỗi chu kỳ vận hành.

## North Star

> Mỗi nội dung phải giải quyết một nhu cầu hoặc câu hỏi cụ thể của một nhóm người cụ thể, dựa trên bằng chứng, có giá trị riêng của MOTGU, có thể đo kết quả và tạo thêm hiểu biết về khách hàng.

## Phạm vi V1

Trong phạm vi:

- MOTGU-first, kiến trúc sẵn sàng mở rộng project sau này;
- Journal;
- Artwork content;
- tiếng Việt và tiếng Anh được viết độc lập từ cùng Brief + Evidence;
- Brand DNA và Language DNA cấu hình được;
- Research + Evidence Ledger;
- durable run harness có checkpoint;
- quality evaluation;
- Content Memory;
- Golden Content + regression;
- Human approval;
- WordPress handoff;
- đo và học theo chu kỳ 1-3-6 tháng.

Ngoài phạm vi V1:

- CRM;
- sales agent;
- customer care agent;
- vận hành đa kênh;
- workflow automation tổng quát;
- multi-project UI;
- tự động thay đổi luật hoặc prompt mà không có người duyệt.

## Tài liệu canonical

Tất cả quyết định sản phẩm và kỹ thuật phải được khóa trong `docs/` trước khi implementation lớn bắt đầu.

Thứ tự đọc:

1. `docs/00-NORTH-STAR.md`
2. `docs/01-NON-NEGOTIABLES.md`
3. `docs/02-ARCHITECTURE-SPEC.md`
4. `docs/03-DATA-CONTRACT.md`
5. `docs/04-SETTINGS-CONTRACT.md`
6. `docs/05-HARNESS-SPEC.md`
7. `docs/06-MEMORY-LEARNING-SPEC.md`
8. `docs/07-QUALITY-EVAL-SPEC.md`
9. `docs/08-JOURNAL-SPEC.md`
10. `docs/09-ARTWORK-SPEC.md`
11. `docs/10-PUBLISH-MEASURE-SPEC.md`
12. `docs/PLAN.md`
13. `docs/TASKS.md`
14. `docs/CHECKLIST.md`
15. `AGENTS.md`

## Kiến trúc tổng quát

```text
Configuration
    ↓
Knowledge + Evidence
    ↓
Durable Harness
    ↓
Content Workflow
    ↓
Human Approval
    ↓
Publish
    ↓
Measure
    ↓
Learning Loop
    ↓
Approved Settings / Memory / Golden Content
```

## Nguyên tắc học từ OpenHuman

ContentEngine học các nguyên lý phù hợp từ OpenHuman, không sao chép toàn bộ sản phẩm hoặc kiến trúc công nghệ:

- nguồn gốc dữ liệu phải truy nguyên được;
- ingest phải chống trùng và có ID ổn định;
- chỉ đưa context liên quan vào model;
- run phải có checkpoint, resume và ledger;
- model/tool call phải có budget và telemetry;
- memory cần lớp raw, summary và retrieval;
- learning chỉ trở thành luật sau khi có evidence và human approval.

Tham khảo: <https://github.com/tinyhumansai/openhuman>

## Trạng thái

`CE00 — Content North Star & Scope`: ACTIVE.

Chưa implementation product code trước khi bộ contract nền được duyệt.
