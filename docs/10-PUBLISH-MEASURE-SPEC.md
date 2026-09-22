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

ContentVersion là immutable. PM-01 không UPDATE `approved → published` và không tạo
một ContentVersion bản sao chỉ để biểu diễn trạng thái WordPress. Publish Package,
PublishedContent, PublishEvent và metrics cùng trỏ về đúng version đã được duyệt.
Trạng thái external nằm ở PublishedContent/PublishEvent.

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
→ create immutable approved ContentVersion
→ create immutable Publish Package
→ WAIT_HUMAN(publish_authorization)
→ Founder publish authorization
→ persist OutboxIntent + deterministic idempotency key
→ mark intent processing and COMMIT DB state
→ worker sends to WordPress outside that DB transaction
→ record confirmed result OR needs_reconciliation
→ reconcile before any resend when outcome is ambiguous
→ save external ID / URL / revision / status
→ append PublishEvent
```

Nếu không biết WordPress đã nhận request hay chưa, phải reconcile trước khi gửi lại.

Final editorial approval và publish authorization là hai quyết định khác nhau. Duyệt nội dung không tự động cấp quyền xuất bản.

`ContentVersion` đã duyệt là immutable. Khi WordPress xác nhận publish, PM-01 giữ
nguyên version đó và ghi external state vào `PublishedContent/PublishEvent`; không
tạo bản sao version chỉ để có `status=published`, và không UPDATE version cũ.

Ranh giới transaction là bắt buộc: trạng thái Outbox `processing` phải được commit trước khi gọi WordPress. Không được giữ một transaction chưa commit xuyên qua external write.

Nếu một ContentItem đang ở trạng thái WordPress `publish`, PM-01 V1 không hạ trực tiếp
bài live về `draft` để review update. Cách đó có thể làm bài biến mất khỏi site.
Update bài live phải đi qua publish authorization riêng; staging/revision workflow là
một nâng cấp khác nếu sau này cần.

Metrics được gắn với đúng `ContentVersion` đã publish. Sau khi có version mới, dữ liệu
muộn của version cũ vẫn được phép ingest nếu có PublishEvent chứng minh version đó từng
được publish.

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
→ PublishedContent → metrics/observations. Chốt expected behaviour, metric definitions,
minimum evidence và review window trước publish. Khi Publish Package được tạo,
mỗi experiment candidate được khóa vào đúng ContentItem/ContentVersion và measurement
contract của candidate đó. Nếu package bị bỏ trước external effect, pipeline có thể tạo
replacement candidate cho cùng version khi measurement contract khác.

Sau external effect, PublishEvent lưu trực tiếp `content_experiment_id`; version/target
đó không được chuyển sang experiment candidate khác trước external dispatch. Measurement
lịch sử vì vậy không phụ thuộc vào trạng thái hiện tại. Measurement status dùng
`INSUFFICIENT_DATA / EARLY_SIGNAL / REPEATED_PATTERN / LEARNING_CANDIDATE_READY`.
Metrics không tự sửa hypothesis hoặc settings.

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

PM-01 tạo `ContentPerformanceObservation` có provenance tới metric/version đã publish.

Bước chuyển Observation → `Signal` → `LearningCandidate` thuộc LL-01. PM-01 không
tự tạo customer truth hay learning rule.

Human review + batch evidence + regression quyết định promote ở Learning Loop.

## 12. Update vs new content

Khi memory cho thấy nội dung cũ có intent giống bài dự kiến, hệ thống đề xuất:

- update existing ContentItem;
- refresh existing ContentItem;
- merge;
- create new cluster với angle rõ khác;
- do not write.

Mọi update tạo ContentVersion mới, không tạo danh tính bài mới tùy tiện.

Memory Gap dùng PublishedContent + latest PublishEvent làm nguồn publish canonical.
Khi có PM-01 identity, REFRESH tính freshness từ thời điểm publish thật; dữ liệu legacy
chưa có mapping/event mới fallback về ContentVersion.created_at.

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