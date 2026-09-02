# CHECKLIST — CONTENTENGINE

## A. Trước khi bắt đầu task

- [ ] Đọc `README.md` và docs liên quan.
- [ ] Xác định phase/task ID.
- [ ] Main sạch và đồng bộ remote.
- [ ] Tạo branch riêng cho task/phase.
- [ ] Ghi rõ GOAL, SCOPE, NON-GOALS.
- [ ] Xác định source of truth bị tác động.
- [ ] Xác định data/API contract bị tác động.
- [ ] Xác định test/evidence cần có trước khi code.
- [ ] Nếu yêu cầu xung đột canonical docs, vào Contract Change Mode trước.

## B. Architecture

- [ ] Logic nằm đúng module owner.
- [ ] Router/controller mỏng.
- [ ] Không import chéo tùy tiện giữa modules.
- [ ] Shared infrastructure chỉ đưa vào `core` khi thật sự dùng chung.
- [ ] Research provider code nằm sau provider seam, không hardcode trong content workflow.
- [ ] Không hardcode business settings/model/prompt production trong workflow.
- [ ] Không tạo generic workflow engine nếu state machine đơn giản đủ dùng.
- [ ] External side effect có idempotency/reconciliation.
- [ ] State transition explicit và test được.

## C. Content identity / song ngữ

- [ ] Có ContentCase cho phần chung.
- [ ] Có LocaleVariant riêng cho từng locale.
- [ ] Không dùng dịch Việt → Anh làm workflow mặc định.
- [ ] Query/Keyword Plan giữ locale riêng, không dịch rồi coi là cùng demand.
- [ ] ContentItem có ID ổn định qua các lần update/refresh.
- [ ] Mỗi lần thay đổi publishable content tạo ContentVersion rõ ràng.
- [ ] Run mode được xác định: create/update/refresh/localize.

## D. Data / provenance

- [ ] Có `project_id` khi resource thuộc project.
- [ ] Có provenance cho knowledge/evidence/media/research signal.
- [ ] Có version/snapshot cho config ảnh hưởng output.
- [ ] Không overwrite lịch sử quan trọng.
- [ ] Có dedupe/fingerprint khi ingest.
- [ ] EvidenceSet bất biến sau khi lock.
- [ ] ContextManifest ghi lại context quan trọng đã đưa vào model.
- [ ] Raw provider result giữ được khi cần audit nhưng không tự thành knowledge truth.
- [ ] Migration strategy rõ.

## E. Harness

- [ ] Step có status/attempt.
- [ ] Output được persist trước state transition.
- [ ] Production job có durable queue/state.
- [ ] Worker claim có lease/heartbeat khi cần.
- [ ] Worker chết có thể reclaim/resume.
- [ ] Retry bounded và dựa trên error class.
- [ ] Budget được enforce.
- [ ] Approval là durable state.
- [ ] Artifact version mới không reuse approval cũ.
- [ ] Tool/model call có telemetry.
- [ ] Side effect có durable intent/outbox hoặc cơ chế tương đương.
- [ ] Kết quả side effect không rõ phải reconciliation trước retry.

## F. Research / Search / Evidence

### Search
- [ ] Internal MOTGU knowledge được kiểm tra trước external web.
- [ ] Serper dùng cho Google discovery signal, không mặc định làm authority judge.
- [ ] Tavily/Exa chỉ gọi khi cần thêm source quality/coverage/depth.
- [ ] Jina chỉ đọc selected URL; không quyết định authority.
- [ ] Brave không được gọi mặc định nếu chưa có lý do coverage/fallback.
- [ ] Không gọi mọi provider cho mọi query.
- [ ] Có provider call budget + stop-when-sufficient.
- [ ] Search position không bị dùng như source quality score.
- [ ] Sales/competitor page được đánh dấu đúng vai trò, không tự thành factual evidence.
- [ ] Second-hop được dùng để tìm source gốc khi nguồn tổng hợp có citation hữu ích.
- [ ] Manual ChatGPT/Gemini Deep Research report không tự thành factual authority; phải theo source URLs.

### Discovery vs Evidence
- [ ] Discovery Research trả lời người đọc/query/gap, không bị dùng nhầm làm factual evidence.
- [ ] Evidence Research kiểm chứng claim.
- [ ] Claim quan trọng map về EvidenceSet.
- [ ] Contradiction không bị che.
- [ ] Authority/freshness rule được áp dụng.
- [ ] Retrieved content giữ provenance.
- [ ] OriginalityPack có nguyên liệu riêng của MOTGU.
- [ ] OriginalityPack quá yếu → research/đổi angle/update/do-not-write.

### Knowledge ingest / Obsidian
- [ ] Raw SERP/API payload không mirror vào Obsidian mặc định.
- [ ] Knowledge Candidate có source refs/provenance.
- [ ] Candidate không tự thành Approved Knowledge.
- [ ] Obsidian note không tự trở thành source of truth chỉ vì tồn tại.

## G. Keyword Plan mini

- [ ] Có seed topic/question rõ.
- [ ] PAA/Related/Autocomplete/organic signals được normalize + dedupe.
- [ ] Question được phân loại theo problem + intent + audience stage khi có thể.
- [ ] Cluster dựa trên answer/problem/intent, không chỉ string similarity.
- [ ] Có kiểm tra existing content trước CREATE.
- [ ] Có pillar/cluster suggestion khi thật sự phù hợp.
- [ ] Có Niche Candidate và giải thích MOTGU Right-to-Win.
- [ ] Có content decision: CREATE/UPDATE/REFRESH/MERGE/LINK_ONLY/DO_NOT_WRITE.
- [ ] Priority dùng NOW/NEXT/LATER/NO với reasons, không giả chính xác 0–100.
- [ ] Mỗi candidate giữ source/signal refs.
- [ ] Human chọn opportunity trước khi đưa sang Golden Journal.

## H. Content

- [ ] Audience rõ.
- [ ] Problem/desire rõ.
- [ ] Intent rõ.
- [ ] Content hypothesis rõ.
- [ ] Reader before/after rõ.
- [ ] Emotional arc hợp lý, không ép cảm xúc giả.
- [ ] Originality rõ và có nguyên liệu cụ thể.
- [ ] Pillar/cluster role rõ.
- [ ] Internal links có ích cho người đọc.
- [ ] Không filler/keyword stuffing.

## I. Artwork / Media

- [ ] Canonical Artwork facts lấy đúng nguồn.
- [ ] Media description map về MediaAsset.
- [ ] Visual claim quan trọng map về approved MediaObservation khi cần.
- [ ] Artist intent có provenance.
- [ ] Price/availability không lấy từ memory stale.

## J. Quality

### Deterministic
- [ ] Required fields đầy đủ.
- [ ] Critical assertion map được về evidence.
- [ ] Canonical facts không drift.
- [ ] Không duplicate/content identity conflict.
- [ ] Source-copy/phrase-overlap không vượt ngưỡng.

### Model-based
- [ ] Reader value pass.
- [ ] Brand voice pass.
- [ ] Originality pass.
- [ ] Reader transformation hợp lý.
- [ ] Language naturalness pass.
- [ ] Search/AI readability pass.

### Human
- [ ] Human final approval có record.
- [ ] Feels like MOTGU được đánh giá.
- [ ] Factual/source-copy concern được ghi nhận.
- [ ] Không tối ưu theo Rank Math overall score.

## K. Learning

- [ ] Human edit delta được lưu khi phù hợp.
- [ ] Output mới không tự thành Golden Example.
- [ ] Calibration Pack/Golden/Weak examples có human approval.
- [ ] Learning chỉ là candidate trước human approval.
- [ ] Candidate có evidence refs, scope và confidence.
- [ ] Có kiểm tra đủ dữ liệu trước khi kết luận.
- [ ] Thay đổi production settings chạy regression.
- [ ] Pairwise candidate vs baseline khi phù hợp.
- [ ] Không tự học từ một tín hiệu đơn lẻ thành global rule.

## L. Measurement

- [ ] Published content map được về ContentItem/Version/Case/Variant.
- [ ] Core metrics được normalize khi cần so sánh.
- [ ] Raw provider payload giữ được khi cần audit.
- [ ] System có thể báo `INSUFFICIENT_DATA`.
- [ ] Rank Math chỉ là technical signal phụ.
- [ ] Search Console query khi đưa lại Keyword Plan chỉ là signal, không tự đổi strategy.

## M. Test

### Backend
- [ ] format/lint pass.
- [ ] type/static checks pass nếu áp dụng.
- [ ] unit tests pass.
- [ ] integration tests pass.
- [ ] OpenAPI generation pass.
- [ ] migration test pass.

### Research
- [ ] provider adapter timeout/error path.
- [ ] provider budget/stop rule.
- [ ] query normalize/dedupe.
- [ ] source refs giữ nguyên qua Keyword Plan.
- [ ] raw SERP không auto-ingest Obsidian.

### Frontend
- [ ] lint pass.
- [ ] typecheck pass.
- [ ] build pass.
- [ ] critical interaction tests pass.

### Workflow
- [ ] happy path.
- [ ] failure path.
- [ ] retry.
- [ ] restart/resume.
- [ ] worker lease reclaim nếu liên quan.
- [ ] approval pause/resume.
- [ ] duplicate protection.
- [ ] ambiguous side-effect reconciliation.
- [ ] ContextManifest reproducibility.

## N. Trước commit

- [ ] `git diff` đã review.
- [ ] Không có secret/API key.
- [ ] Không có debug/temp file.
- [ ] Docs cập nhật nếu contract đổi.
- [ ] Tests/evidence ghi lại được.
- [ ] Commit message mô tả đúng mục tiêu.

## O. Trước PR

PR report:

```text
GOAL

FILES CHANGED

EVIDENCE

RISKS / BLOCKERS

STATUS

NEXT
```

- [ ] PR nhỏ, một mục tiêu chính.
- [ ] CI pass.
- [ ] Không merge khi còn unresolved contract issue.
- [ ] Review comments được xử lý hoặc giải thích.

## P. Sau merge

- [ ] Đồng bộ main.
- [ ] Xác minh local main = origin/main.
- [ ] Working tree sạch.
- [ ] Xóa task branch khi phù hợp.
- [ ] Chạy post-merge smoke test.
- [ ] Cập nhật TASKS phase state.
- [ ] Chỉ bắt đầu task tiếp theo sau checkpoint/review.
