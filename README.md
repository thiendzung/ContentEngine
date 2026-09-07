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

Planning contract: MARKET / SEARCH / MOTGU Signal → NeedHypothesis → Opportunity Map
→ human selection → Research + MOTGU material → Journal/Artwork → ContentExperiment
→ Measure → reviewed hypothesis revision. Keyword Plan là công cụ con trong Research.
PR #5 cập nhật contract và Jina reader trước real-seed Gate B; PR-C là Opportunity Map
Mini. Seed ban đầu là founder-proposed need hypothesis, chưa phải customer truth.

> Mỗi nội dung phải giải quyết một nhu cầu hoặc câu hỏi cụ thể của một nhóm người cụ thể, dựa trên bằng chứng, có giá trị riêng của MOTGU, có thể đo kết quả và tạo thêm hiểu biết về khách hàng.

## Local quickstart

```bash
cp .env.example .env
make setup
make db-up
make migrate
```

Chạy backend:

```bash
make backend-dev
```

Chạy frontend ở terminal khác:

```bash
make frontend-dev
```

Kiểm tra:

- frontend: `http://localhost:3000`
- backend health: `http://localhost:8000/health`
- backend database health: `http://localhost:8000/health/db`
- backend version: `http://localhost:8000/version`

Chạy bộ kiểm tra:

```bash
make types
make check
```

Không commit `.env` hoặc API key thật.

## Phạm vi V1

Trong phạm vi:

- MOTGU-first, kiến trúc sẵn sàng mở rộng project sau này;
- Journal;
- Artwork content;
- tiếng Việt và tiếng Anh dùng chung ContentCase/Evidence nhưng có LocaleVariant và cách viết riêng;
- Brand DNA và Language DNA cấu hình được;
- Discovery Research + Evidence Research;
- Search stack tiết kiệm: Serper + Tavily + Exa + Jina, Brave chỉ fallback/coverage check;
- Opportunity Map mini với Keyword/Question Map là công cụ con;
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
- database keyword hàng chục nghìn từ;
- backlink/keyword-difficulty suite;
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
12. `docs/11-RESEARCH-SEARCH-SPEC.md`
13. `docs/12-OPPORTUNITY-MAP-SPEC.md`
14. `docs/PLAN.md`
15. `docs/TASKS.md`
16. `docs/CHECKLIST.md`
17. `docs/CE01-WALKING-SKELETON-RUNBOOK.md`
18. `AGENTS.md`

## Kiến trúc tổng quát

```text
Configuration
    ↓
ContentCase + LocaleVariant
    ↓
Knowledge Recall
    ↓
Discovery Research
    ↓
Keyword / Question / Opportunity Map
    ↓
Evidence Research
    ↓
EvidenceSet + OriginalityPack
    ↓
Durable Harness
    ↓
Content Workflow
    ↓
Assertion Audit + Human Approval
    ↓
Publish
    ↓
Measure
    ↓
Learning Loop
    ↓
Approved Settings / Memory / Golden Content
```

## Search stack V1

```text
Serper
→ nhìn Google: PAA / Related / Autocomplete / organic

Tavily
→ tìm nguồn nghiên cứu phù hợp khi Google nhiều sales/SEO noise

Exa
→ tìm nguồn sâu, nguồn tương tự và second-hop

Jina
→ đọc sạch các URL đã chọn

Brave
→ optional fallback / coverage check
```

Không dùng search ranking như thước đo độ tin cậy của nguồn.

## Knowledge sau research

Không đổ raw SERP/API data vào Obsidian.

```text
Raw source
→ Knowledge Candidate
→ dedupe + provenance + review
→ Approved Knowledge
→ Obsidian mirror khi hữu ích
```

Obsidian là workspace/mirror dễ đọc cho người, không tự trở thành source of truth chỉ vì một note tồn tại.

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

- `CE00 — Foundation Contracts`: CLOSED.
- `CE01 — Repository Skeleton + Research Spike + Walking Skeleton`: CLOSED / PASS.
- `CE02 — Core Data + Settings`: CLOSED / PASS.
- `CE03 — Durable Harness`: CLOSED / PASS.
- `CE03 PR-A — Durable Queue + Lease Core`: CLOSED / MERGED / PASS.
- `CE03 PR-B — Checkpoint + Approval + Retry + Budget`: CLOSED / MERGED / PASS.
- `CE03 PR-C — ModelRouter + ToolAdapter + ContextManifest + Telemetry`: CLOSED / MERGED / PASS.
- `CE03 PR-D — Outbox + Reconciliation + Restart/Resume`: CLOSED / MERGED / PASS.
- `CE03 PR-E — Replay/Eval + CE03 Closeout`: CLOSED / MERGED / PASS.
- `CE04 — Knowledge + Production Research`: ACTIVE.
- `CE04 PR-A — Source Ingest + Dedupe + Chunking`: CLOSED / MERGED / PASS.
- `CE04 PR-B — Entity Linking + Retrieval + Authority Ranking`: CLOSED / MERGED / PASS.
- `CE04 PR-C — Production ResearchRouter + Provider Adapters`: CLOSED / MERGED / PASS.
- Current PR: none.
- Current implementation slice: `none — neutral checkpoint after CE04 PR-C`.
- Next planned slice: `CE04 PR-D — Discovery Research + Opportunity Handoff` — PLANNED / NOT STARTED.

CE03 PR-A đã khóa queue/lease core. PR-B bổ sung checkpoint versioned, approval pause/resume theo exact artifact, bounded retry và budget theo run/step mà không tạo nguồn trạng thái thứ hai. PR-C đã hoàn tất ModelRouter, ToolAdapter, ContextManifest và telemetry. PR-D đã hoàn tất outbox, reconciliation và restart/resume. PR-E đã hoàn tất Replay/Eval và CE03 closeout. CE03 đã CLOSED / PASS. CE04 PR-A và PR-B đã CLOSED / MERGED / PASS. CE04 PR-C đã CLOSED / MERGED / PASS trong PR #24 với merge commit `39731375a5a90f3a6e590ed3c856d973d5feb1b9`; T04.9–T04.14 đã hoàn tất implementation + real-run Gate C. Repo đang ở neutral checkpoint; không bắt đầu PR-D trước khi có scope và branch được kích hoạt sau post-merge verification.
