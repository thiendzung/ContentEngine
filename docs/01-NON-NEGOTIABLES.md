# 01 — NON-NEGOTIABLES

Các luật dưới đây là bắt buộc cho V1. Mọi implementation, prompt, workflow và UI phải tuân theo.

## 1. MOTGU-first, không làm multi-project UI trong V1

- Có `project_id` trong data contract để tránh khóa kiến trúc.
- V1 chỉ có project `motgu`.
- Không xây màn quản lý nhiều project, phân quyền nhiều project hoặc workflow đa tenant.

## 2. Source of truth phải rõ ràng

Không có một “AI memory” được phép tự trở thành nguồn sự thật.

Ví dụ:

- dữ liệu Artwork hiện tại → WordPress/WooCommerce canonical source;
- Brand DNA → approved project settings/knowledge;
- research bên ngoài → evidence source;
- giá/tồn kho hiện tại → hệ thống vận hành trực tiếp, không lấy từ memory cũ.

## 3. Evidence before assertion

Một claim factual quan trọng chỉ được xuất bản khi:

- có evidence hợp lệ; hoặc
- được đánh dấu rõ là opinion/interpretation; hoặc
- do MOTGU cung cấp và có authority phù hợp.

Không dùng quy trình “viết trước rồi tìm nguồn để hợp thức hóa”.

Final content phải qua assertion audit để phát hiện factual statement mới không nằm trong evidence đã khóa.

## 4. Provenance bắt buộc

Mọi knowledge item, evidence, content memory và learning phải giữ được:

- source;
- source type;
- source locator;
- created/updated time;
- authority;
- version hoặc fingerprint khi có thể.

## 5. Human approval ở checkpoint quan trọng

Tối thiểu phải có người duyệt ở:

- selected angle hoặc approved outline;
- final content trước publish;
- learning candidate trước khi promote thành rule/settings;
- Golden Content trước khi dùng làm regression baseline.

## 6. Không tự học thành luật

AI có thể tạo `learning_candidate` nhưng không được tự:

- sửa Brand DNA;
- thay đổi Quality Gate;
- thay đổi Writing Recipe;
- thay prompt canonical;
- nâng một bài thành Golden Content.

Cần human approval và evidence.

## 7. Durable run, không workflow mù

Mỗi run phải có:

- `run_id`;
- state rõ;
- checkpoint;
- input snapshot;
- settings version;
- context manifest;
- model/tool call ledger;
- output từng bước;
- error/retry state.

Run phải có khả năng resume từ checkpoint phù hợp.

## 8. Idempotency và chống trùng

Các thao tác ingest và publish phải thiết kế để chạy lại không tạo bản trùng ngoài ý muốn.

Nguồn giống nhau phải có stable fingerprint hoặc deterministic ID để dedupe.

Worker/job chạy lại cũng không được làm side effect lặp.

## 9. Context có giới hạn

Không đẩy toàn bộ knowledge/content memory vào model.

Mỗi task chỉ nhận context tối thiểu cần thiết:

- Brand/Language DNA liên quan;
- Brief/Locale Variant;
- evidence đã chọn;
- content memory có liên quan;
- số Golden Examples giới hạn.

Mọi context quan trọng phải có ID/hash để truy lại được model đã nhìn thấy gì.

## 10. Prompt và Settings phải versioned

Mọi output quan trọng phải truy ra được:

- prompt version;
- settings version;
- recipe version;
- model;
- evidence set;
- context manifest.

Không được có nhiều nguồn sự thật cho cùng một setting/prompt.

## 11. Quality không đồng nghĩa điểm SEO plugin

Rank Math hoặc công cụ tương tự là nguồn tín hiệu kỹ thuật phụ.

Không được dùng score plugin làm mục tiêu tối thượng hoặc tự động publish chỉ vì đạt điểm cao.

## 12. Search/AI optimization không được làm hỏng người đọc

Không:

- nhồi từ khóa;
- tạo FAQ vô ích;
- kéo dài bài để tăng word count;
- chia nhỏ câu chỉ để bot đọc;
- lặp entity/thực thể quá mức;
- tạo nội dung không có giá trị riêng.

## 13. Originality Gate bắt buộc

Mỗi content case phải trả lời:

> MOTGU có thể nói điều gì ở bài này mà một bài tổng hợp chung trên Internet không thể nói tốt bằng?

Writer phải nhận một `OriginalityPack` cụ thể, không chỉ một câu mô tả chung.

Nếu không có nguyên liệu riêng đủ tốt, ưu tiên research thêm, đổi angle, cập nhật nội dung cũ hoặc không viết.

## 14. Content identity phải bền qua thời gian

Không coi mỗi lần sửa bài là một bài mới.

Hệ thống phải phân biệt:

- ý tưởng/content case;
- bản ngôn ngữ;
- content item ổn định;
- version của content item;
- run tạo hoặc cập nhật version đó.

Điều này là bắt buộc để đo hiệu quả và học đúng sau 1–3–6 tháng.

## 15. Regression trước promotion

Thay đổi lớn ở:

- prompt;
- model;
- recipe;
- Brand DNA;
- retrieval;
- quality evaluator;

phải chạy regression trên Golden Set trước khi promote production.

Regression ưu tiên so sánh candidate với baseline, không chỉ nhìn một điểm số tuyệt đối.

## 16. Observability và cost là một phần của product

Mỗi run phải đo tối thiểu:

- latency;
- token/input-output usage khi provider cung cấp;
- cost ước tính/thực tế;
- retries;
- tool failures;
- evaluator results;
- human edit delta.

Không tối ưu cost bằng cách làm giảm chất lượng dưới gate.

## 17. Contract Change Mode

Nếu yêu cầu mới xung đột với tài liệu canonical:

1. xác định rõ conflict;
2. coi đây là thay đổi contract;
3. cập nhật tài liệu canonical cùng task hoặc trước implementation;
4. chỉ code sau khi contract mới rõ.

Không silently bypass tài liệu chỉ vì một cách làm nhanh hơn.

## 18. Chất lượng phải được kiểm chứng sớm

Không đợi xây xong toàn bộ hạ tầng mới thử chất lượng bài viết.

Ngay giai đoạn đầu phải có một đường rất mỏng:

```text
Real Brief
+ Manual Evidence
+ Real Brand Examples
→ Angle
→ Outline
→ Draft
→ Human Review
```

Nếu đường này không tạo ra nội dung đáng đăng, phải sửa content contract trước khi mở rộng hạ tầng.
