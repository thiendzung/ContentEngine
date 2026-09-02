# 10 — PUBLISH & MEASURE SPEC

## 1. Mục tiêu

Đưa nội dung đã duyệt sang WordPress MOTGU an toàn, chống trùng và gắn được measurement identity để học sau publish.

## 2. Publish package

Mỗi package tối thiểu có:

- project/content ID;
- content type;
- locale;
- title;
- slug;
- body;
- excerpt/meta description;
- canonical entities;
- internal links;
- media references;
- structured-data recommendation;
- final artifact hash;
- approval reference;
- content hypothesis ID.

## 3. WordPress adapter

Adapter phải:

- idempotent;
- validate target/content type;
- hỗ trợ draft trước publish;
- lưu mapping internal ID ↔ WordPress ID;
- không overwrite thay đổi ngoài hệ thống nếu chưa reconciliation;
- trả canonical URL và post status.

V1 ưu tiên handoff/draft an toàn trước full auto-publish.

## 4. Rank Math

Rank Math Pro dùng như nguồn kiểm tra phụ sau khi content lên WordPress.

Các signal hữu ích được normalize khi có cách truy cập ổn định:

- metadata/config warning;
- on-page hygiene;
- indexability-related checks;
- technical SEO findings.

Không lưu overall Rank Math score như mục tiêu kinh doanh chính.

## 5. Measurement sources

Ưu tiên:

### Search Console
- queries;
- impressions;
- clicks;
- CTR;
- average position;
- page/query mapping.

### Analytics
- landing sessions/users;
- engagement signals phù hợp;
- transitions sang Artist/Artwork/Visit/Workshop;
- return visits khi đo được hợp lệ.

### MOTGU conversion events
- artwork inquiry;
- visit intent/action;
- workshop intent/action;
- other approved business events.

## 6. Measurement identity

Mỗi published content phải map được:

```text
PublishedContent
↔ canonical_url
↔ content_hypothesis
↔ audience_hypothesis
↔ problem/desire
↔ intent
↔ content role
```

Nếu không map được thì dữ liệu traffic khó biến thành learning.

## 7. Snapshot cadence

Khuyến nghị snapshot theo cửa sổ:

- early: 7/14/30 ngày;
- learning: tháng 1;
- pattern: tháng 3;
- narrowing: tháng 6.

Điều chỉnh theo lượng traffic thực tế; tránh kết luận mạnh từ mẫu quá nhỏ.

## 8. Learning output

Measurement không tự sửa content strategy.

Nó tạo:

- `AudienceSignal`;
- `ContentPerformanceObservation`;
- `LearningCandidate`.

Human review + batch evidence quyết định promote.

## 9. Update vs new content

Khi memory cho thấy nội dung cũ đã có intent giống bài dự kiến, hệ thống phải cho phép đề xuất:

- update existing;
- merge;
- create new cluster với angle khác;
- do not write.

## 10. Definition of done

Publish/Measure V1 đạt khi:

- publish mapping idempotent;
- final approval bắt buộc;
- URL/content ID gắn được metrics;
- Search/Analytics signals normalize được;
- Rank Math chỉ là technical signal;
- learning output trace về content hypothesis ban đầu.
