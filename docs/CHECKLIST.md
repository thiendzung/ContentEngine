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

## B. Architecture

- [ ] Logic nằm đúng module owner.
- [ ] Router/controller mỏng.
- [ ] Không import chéo tùy tiện giữa modules.
- [ ] Shared infrastructure nằm ở `core` phù hợp.
- [ ] Không hardcode business settings/model names trong workflow.
- [ ] External side effect có idempotency/reconciliation.
- [ ] State transition explicit và test được.

## C. Data

- [ ] Có `project_id` khi resource thuộc project.
- [ ] Có provenance cho knowledge/evidence.
- [ ] Có version/snapshot cho config ảnh hưởng output.
- [ ] Không overwrite lịch sử quan trọng.
- [ ] Có dedupe/fingerprint khi ingest.
- [ ] Migration forward/backward strategy rõ.

## D. Harness

- [ ] Step có status/attempt.
- [ ] Output được persist trước state transition.
- [ ] Restart có thể resume.
- [ ] Retry bounded và dựa trên error class.
- [ ] Budget được enforce.
- [ ] Approval là durable state.
- [ ] Artifact version mới không reuse approval cũ.
- [ ] Tool/model call có telemetry.

## E. Research / Evidence

- [ ] Internal knowledge được kiểm tra trước external web.
- [ ] Claim quan trọng map về evidence.
- [ ] Contradiction không bị che.
- [ ] Authority rule được áp dụng.
- [ ] Không viết fact mới ngoài locked evidence.
- [ ] Retrieved content giữ provenance.

## F. Content

- [ ] Audience rõ.
- [ ] Problem/desire rõ.
- [ ] Intent rõ.
- [ ] Content hypothesis rõ.
- [ ] Originality statement rõ.
- [ ] Pillar/cluster role rõ.
- [ ] Locale writer độc lập, không dịch máy mặc định.
- [ ] Internal links có ích cho người đọc.

## G. Quality

- [ ] Evidence gate pass.
- [ ] Reader value pass.
- [ ] Brand truth pass.
- [ ] Originality pass.
- [ ] Language naturalness pass.
- [ ] Search/AI readability pass.
- [ ] Không tối ưu theo Rank Math overall score.
- [ ] Human final approval có record.

## H. Learning

- [ ] Human edit delta được lưu khi phù hợp.
- [ ] Output mới không tự thành Golden Example.
- [ ] Learning chỉ là candidate trước human approval.
- [ ] Candidate có evidence refs.
- [ ] Thay đổi production settings chạy regression.
- [ ] Không tự học từ một tín hiệu đơn lẻ thành global rule.

## I. Test

### Backend
- [ ] format/lint pass.
- [ ] type/static checks pass nếu áp dụng.
- [ ] unit tests pass.
- [ ] integration tests pass.
- [ ] OpenAPI generation pass.
- [ ] migration test pass.

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
- [ ] approval pause/resume.
- [ ] duplicate protection.

## J. Trước commit

- [ ] `git diff` đã review.
- [ ] Không có secret/API key.
- [ ] Không có debug/temp file.
- [ ] Docs cập nhật nếu contract đổi.
- [ ] Tests/evidence ghi lại được.
- [ ] Commit message mô tả đúng mục tiêu.

## K. Trước PR

PR report phải có:

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

## L. Sau merge

- [ ] Đồng bộ main.
- [ ] Xác minh local main = origin/main.
- [ ] Working tree sạch.
- [ ] Xóa task branch khi phù hợp.
- [ ] Chạy post-merge smoke test.
- [ ] Cập nhật TASKS phase state.
- [ ] Chỉ bắt đầu task tiếp theo sau checkpoint/review.
