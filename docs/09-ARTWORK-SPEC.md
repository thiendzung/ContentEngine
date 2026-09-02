# 09 — ARTWORK SPEC

## 1. Mục tiêu

Artwork content phải vừa là trang sản phẩm có facts rõ, vừa là trang kiến thức và trust page cho người đang cân nhắc xem/mua tác phẩm.

## 2. Content identity

Artwork content cũng dùng:

```text
ContentCase
→ LocaleVariant
→ ContentItem
→ ContentVersion
```

Khi sửa nội dung Artwork, không tạo bài mới nếu vẫn là cùng một trang/tác phẩm và cùng locale.

## 3. Required inputs

- canonical Artwork entity;
- Artist entity;
- verified material/size/year/status;
- MediaAsset refs;
- MediaObservation đã được chấp nhận khi dùng mô tả hình ảnh;
- related Journal/Artist links;
- audience/problem hypothesis nếu có;
- locale;
- source authority map;
- EvidenceSet;
- OriginalityPack.

## 4. Questions phải trả lời

Tùy tác phẩm, ưu tiên:

- đây là tác phẩm gì;
- ai làm;
- chất liệu/kích thước/năm;
- người xem đang nhìn thấy gì;
- yếu tố thị giác/chất liệu nào đáng chú ý;
- context nào được artist/MOTGU xác nhận;
- tác phẩm có duy nhất không;
- practical info: viewing, shipping, availability nếu canonical source cung cấp;
- nội dung liên quan nào giúp hiểu sâu hơn.

## 5. Phân biệt 4 loại phát biểu

Không trộn lẫn:

- `factual property` — dữ liệu canonical;
- `verified artist intent` — ý định nghệ sĩ có nguồn;
- `visual observation` — điều nhìn thấy từ MediaAsset cụ thể;
- `MOTGU editorial interpretation` — diễn giải của MOTGU, không trình bày như fact.

Nếu ý định nghệ sĩ không có nguồn, không viết như fact.

## 6. Source priority

Artwork factual fields ưu tiên canonical WordPress/WooCommerce/MOTGU source.

External web không được override:

- title;
- artist;
- medium;
- dimensions;
- availability;
- price;
- edition/uniqueness;
- official story.

Live fields như price/availability phải lấy lại từ hệ thống vận hành phù hợp khi package/publish cần dùng; không dùng memory stale.

## 7. Media Evidence

Mọi mô tả chi tiết từ ảnh phải truy được về `MediaAsset`.

`MediaObservation` phải ghi:

- asset nào;
- observation gì;
- do human/model/metadata tạo;
- confidence;
- approved/candidate/rejected.

Model observation chưa approved không được tự trở thành canonical fact.

Nếu ảnh không đủ rõ để kết luận, writer phải dùng ngôn ngữ thận trọng hoặc bỏ chi tiết đó.

## 8. Content structure

Không template cứng, nhưng package phải có:

- immediate orientation;
- factual block;
- visual/material reading;
- artist/context connection;
- practical trust information;
- related links;
- clear next action.

## 9. Artwork originality

`OriginalityPack` ưu tiên:

- artwork-specific observation;
- artist-approved story;
- studio/process context;
- real image details;
- verified provenance/context;
- practical MOTGU experience.

Nếu chỉ có generic artist biography và facts cơ bản, cần bổ sung nguyên liệu trước khi viết dài.

## 10. Assertion Audit

Sau Draft/Revision:

- canonical facts phải khớp source;
- artist intent phải có provenance;
- visual observation phải map MediaObservation;
- practical/live info phải có source phù hợp;
- unsupported critical assertion → block.

## 11. Search/AI clarity

Entity phải rõ:

- artwork name;
- artist;
- medium;
- dimensions;
- year;
- canonical URL;
- related artist/artwork/journal entities.

Structured data chỉ phản ánh dữ liệu thật trên trang.

## 12. Bilingual

Cùng ContentCase/core facts/evidence, writer riêng theo LocaleVariant.

Tên riêng, medium hoặc thuật ngữ có canonical translation map nếu cần.

Không tự dịch tên tác phẩm nếu MOTGU chưa định nghĩa translation policy.

## 13. Final package

Tối thiểu:

- ContentCase/LocaleVariant/ContentItem refs;
- canonical Artwork/Artist refs;
- title/slug/body/meta;
- factual block;
- media refs;
- related content links;
- EvidenceSet ref;
- Assertion Audit ref;
- structured-data recommendation;
- measurement plan.

## 14. Hard fails

- sai canonical facts;
- bịa artist intent;
- dùng scarcity giả;
- mô tả ảnh không map về MediaAsset/approved observation;
- price/availability lấy từ memory stale;
- unsupported factual assertion;
- copy/paraphrase quá sát nguồn;
- copy generic artist biography thay vì artwork-specific value.
