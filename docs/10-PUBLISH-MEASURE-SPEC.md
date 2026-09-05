# 10 — PUBLISH & MEASURE SPEC

## 1. Mục tiêu

Đưa nội dung đã duyệt sang WordPress MOTGU an toàn, chống trùng và gắn được measurement identity để học sau publish.

## 2. Publish package

Mỗi package tối thiểu có:

- project ID;
- ContentCase ID;
- LocaleVariant ID;
- ContentItem ID;
- ContentVersion ID;
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
- EvidenceSet/Assertion Audit refs;
- approval reference;
- content hypothesis ID.

## 3. WordPress adapter

Adapter phải:

- idempotent;
- validate target/content type;
- hỗ trợ draft trước publish;
- lưu mapping `ContentItem ↔ WordPress ID`;
- lưu lịch sử ContentVersion nào đã đẩy;
- không overwrite thay đổi ngoài hệ thống nếu chưa reconciliation;
- trả canonical URL/post status/revision khi có.

V1 ưu tiên handoff/draft an toàn trước full auto-publish.

## 4. Publish flow an toàn

```text
Final Human Approval
→ create ContentVersion
→ persist publish intent + idempotency key
→ worker sends to WordPress
→ reconcile WordPress result
→ save external ID/revision
→ mark PublishEvent complete
```

Nếu không biết WordPress đã nhận request hay chưa, phải reconcile trước khi gửi lại.

## 5. Rank Math

Rank Math Pro dùng như nguồn kiểm tra phụ sau khi content lên WordPress.

Signal hữu ích khi có cách truy cập ổn định:

- metadata/config warning;
- on-page hygiene;
- indexability-related checks;
- technical SEO findings.

Không lưu/đẩy overall score thành mục tiêu kinh doanh chính.

## 6. Measurement sources

### Search Console

- queries;
- impressions;
- clicks;
- CTR;
- average position;
- page/query mapping.

### Analytics

- landing sessions/users;
- engagement phù hợp;
- transitions sang Artist/Artwork/Visit/Workshop;
- return visits khi đo được hợp lệ.

### MOTGU conversion events

- artwork inquiry;
- visit intent/action;
- workshop intent/action;
- other approved business events.

## 7. Normalized core metrics

Không chỉ lưu một JSON blob khó so sánh.

V1 chuẩn hóa ít nhất:

- `impressions`;
- `clicks`;
- `sessions`;
- `engaged_sessions`;
- `artwork_transition`;
- `visit_transition`;
- `workshop_transition`;
- `inquiry`.

Raw provider payload vẫn được giữ khi cần audit/debug.

## 8. Measurement identity

ContentExperiment nối ContentOpportunity → NeedHypothesis version → ContentItem/Version
→ PublishedContent → metrics/Signal observations. Chốt expected behaviour và review window
trước publish; thiếu dữ liệu = INCONCLUSIVE. Metrics không tự sửa hypothesis hoặc settings.

Mỗi published content map được:

```text
PublishedContent / ContentItem
↔ ContentVersion
↔ canonical_url
↔ ContentCase
↔ LocaleVariant
↔ content_hypothesis
↔ audience_hypothesis
↔ problem/desire
↔ intent
↔ content role/topic relation
```

Nếu không map được thì traffic khó biến thành learning.

## 9. Snapshot cadence

Khuyến nghị:

- early: 7/14/30 ngày;
- learning: tháng 1;
- pattern: tháng 3;
- narrowing: tháng 6.

Điều chỉnh theo traffic thực tế.

Không kết luận mạnh từ mẫu nhỏ.

## 10. Sufficiency / đủ dữ liệu để học

Measurement phải có khả năng báo:

- `INSUFFICIENT_DATA`;
- `EARLY_SIGNAL`;
- `REPEATED_PATTERN`;
- `LEARNING_CANDIDATE_READY`.

Rule có thể dùng:

- minimum sample;
- minimum time window;
- minimum repeated observations;
- required conversion/search signal.

Không tự biến một bài thắng/thua thành thay đổi strategy.

## 11. Learning output

Measurement tạo:

- `Signal`;
- `ContentPerformanceObservation`;
- `LearningCandidate`.

Human review + batch evidence + regression quyết định promote.

## 12. Update vs new content

Khi memory cho thấy nội dung cũ có intent giống bài dự kiến, hệ thống đề xuất:

- update existing ContentItem;
- refresh existing ContentItem;
- merge;
- create new cluster với angle rõ khác;
- do not write.

Mọi update tạo ContentVersion mới, không tạo danh tính bài mới tùy tiện.

## 13. Definition of done

Publish/Measure V1 đạt khi:

- ContentItem ↔ WordPress mapping idempotent;
- ContentVersion publish history rõ;
- final approval bắt buộc;
- side-effect không tạo duplicate khi retry;
- URL/content ID gắn được metrics;
- core metrics được normalize;
- Rank Math chỉ là technical signal;
- learning trace về content hypothesis ban đầu;
- system biết nói khi dữ liệu chưa đủ để kết luận.
