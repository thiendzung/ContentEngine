# 08 — JOURNAL SPEC

## 1. Mục tiêu

Journal giải quyết một nhu cầu nhỏ nhưng thật của một nhóm người cụ thể, đồng thời tạo đường nối tự nhiên tới MOTGU knowledge/entities.

Journal không bắt đầu từ keyword đơn lẻ. Nó bắt đầu từ `ContentCase`: ai đang cần gì, tại sao đáng viết, và MOTGU có điều gì riêng để đóng góp.

## 2. ContentCase — phần chung

Mỗi Journal case phải có:

- audience hypothesis;
- problem/desire/question;
- desired action;
- content hypothesis;
- originality statement;
- reader before;
- reader after;
- canonical facts/evidence scope;
- relation tới bài cũ nếu là update/refresh.

## 3. LocaleVariant — phần riêng theo ngôn ngữ

Mỗi `vi-VN` hoặc `en` variant có:

- content role: pillar/cluster;
- primary question;
- primary/secondary intent;
- query/keyword notes;
- emotional arc;
- must-include;
- must-not-claim;
- Language DNA/recipe selection.

Không dịch một variant để tạo variant kia như workflow mặc định.

## 4. Research phải tách 2 mục tiêu

### A. Discovery Research — hiểu người đọc và khoảng trống nội dung

Trả lời:

- người đọc đang hỏi gì;
- dùng cách nói/từ nào;
- nỗi lo/phản đối nào xuất hiện;
- Search hiện trả lời ra sao;
- competitor/content hiện có đang thiếu gì;
- MOTGU Content Memory đã có gì;
- nên create/update/refresh/merge/do-not-write?

Nguồn có thể gồm Search query, SERP, forum/community, customer/visitor questions, analytics và content memory.

Discovery Research không tự trở thành factual evidence cho claim.

### B. Evidence Research — kiểm chứng điều sẽ viết

Trả lời:

- claim nào cần chứng minh;
- nguồn primary/high-trust nào hỗ trợ;
- có nguồn phản bác không;
- authority/freshness đủ không;
- claim nào phải bỏ hoặc đổi thành interpretation/opinion.

Output cuối: `EvidenceSet` bất biến cho run/version.

## 5. Research order đề xuất

```text
MOTGU internal knowledge
→ Content Memory check
→ Discovery Research
→ define gaps/claims
→ Evidence Research
→ EvidenceSet
→ OriginalityPack
```

Không web-search rộng trước khi biết MOTGU đã có gì và người đọc cần gì.

## 6. Originality Pack

Trước Angle/Draft, Journal phải có nguyên liệu riêng cụ thể.

Có thể gồm:

- MOTGU first-party fact;
- artist quote;
- artwork/studio/process observation;
- visitor/customer question;
- practical MOTGU experience;
- synthesis mới dựa trên evidence.

Nếu pack quá yếu, ưu tiên research thêm, đổi angle, update bài cũ hoặc không viết.

## 7. Angle selection

Mỗi angle mô tả:

- reader promise;
- reader transformation;
- emotional direction;
- originality;
- evidence coverage;
- MOTGU connection;
- risks.

Không chọn angle chỉ vì “creative”.

## 8. Outline contract

Outline phải:

- trả lời primary question sớm khi phù hợp;
- mỗi section có purpose;
- map section → evidence/knowledge refs;
- đánh dấu phần MOTGU-original;
- xác định internal-link targets;
- thể hiện reader transformation;
- tránh filler.

## 9. Draft contract

Writer chỉ được dùng:

- locked EvidenceSet;
- approved knowledge;
- OriginalityPack;
- explicit interpretation/opinion;
- bounded Content Memory/Golden examples.

Nếu cần factual claim mới:

- đánh dấu unresolved;
- không invent;
- route về Evidence Research nếu cần thiết.

## 10. Assertion Audit

Sau Draft/Revision:

```text
content
→ extract important assertions
→ map về Claim/EvidenceSet
→ flag unsupported/contradicted
```

Critical unsupported assertion không được sang Final Approval.

## 11. Bilingual contract

`vi-VN` và `en` dùng chung ContentCase/core facts/evidence nhưng có LocaleVariant và draft riêng.

Không yêu cầu sentence-level equivalence.

Phải giữ equivalence ở:

- factual truth;
- brand position;
- core reader value;
- entity identity;
- content hypothesis cốt lõi.

## 12. Pillar vs Cluster

### Pillar

- broad orientation;
- nhiều subquestions;
- hub cho internal links;
- cập nhật theo thời gian;
- không cover mọi ngách quá sâu.

### Cluster

- một vấn đề/query hẹp;
- answer cụ thể;
- link về pillar/entity liên quan;
- tránh cạnh tranh intent với cluster khác.

Pillar/cluster relation phải lưu được bằng TopicNode/ContentRelation sau khi ContentItem tồn tại.

## 13. Internal linking

Link phải có lý do cho người đọc.

Ưu tiên:

- related Artwork;
- Artist;
- Workshop;
- Visit;
- pillar/cluster hỗ trợ.

Không thêm link để đạt số lượng.

## 14. Final package

Tối thiểu:

- ContentCase/LocaleVariant/ContentItem refs;
- title;
- slug suggestion;
- excerpt/meta description;
- body;
- headings;
- primary/secondary entities;
- internal links;
- image brief/alt suggestions grounded in actual media khi có;
- structured-data recommendation;
- EvidenceSet ref;
- Assertion Audit ref;
- content hypothesis ID;
- measurement plan.

## 15. Walking Skeleton Journal

Bài thật đầu tiên phải được tạo trước khi toàn bộ auto-research/memory hoàn thiện.

Cho phép dùng:

- Manual ContentCase;
- Manual LocaleVariant;
- Manual EvidenceSet;
- Manual OriginalityPack;
- real Calibration examples.

Mục tiêu: kiểm chứng chất lượng content contract, không kiểm chứng hạ tầng.

## 16. Journal hard fails

- không rõ ai đọc;
- không rõ vấn đề;
- generic web summary;
- OriginalityPack quá yếu;
- unsupported factual assertion;
- invented artist/brand story;
- source-copy/paraphrase quá sát;
- translation-like English/Vietnamese;
- CTA không liên quan;
- trùng intent đáng kể với bài đang có mà không có lý do update/new angle.
