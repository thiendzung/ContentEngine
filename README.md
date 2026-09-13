# ContentEngine

ContentEngine là hệ thống sản xuất và học từ nội dung cho MOTGU. Mục tiêu đầu tiên là Journal và Artwork content chất lượng cao, tiếng Việt/tiếng Anh theo cấu hình, để xuất bản lên WordPress MOTGU.

Không tối ưu số lượng bài. Ưu tiên giá trị thật với người đọc, độ đúng và nguồn gốc, giọng MOTGU, khả năng Search/AI hiểu, bước tiếp theo phù hợp sang Artist/Artwork/Visit/Workshop/Inquiry và khả năng học từ kết quả.

## Hoàn thành trước, hoàn thiện sau

`Một Journal thật được duyệt -> chạy lặp lại trên máy local -> đưa bài lên web và đo -> cải tiến theo bằng chứng`

Ứng dụng và DB vận hành trên máy Founder. Research/model vẫn cần mạng và quyền truy cập hợp lệ; đây không phải cam kết chạy hoàn toàn ngoại tuyến.

- [Spec vận hành local](docs/20-LOCAL-FIRST-DELIVERY-SPEC.md)
- [Lộ trình](docs/PLAN.md)
- [Task và tiến độ](docs/TASKS.md)
- [Checklist](docs/CHECKLIST.md)
- [Góc nhìn chung hiện tại](AI_context.MD)
- [Vai trò và quy tắc phối hợp](AGENTS.md)

GitHub giữ mã, quyết định và bằng chứng đã lược bỏ dữ liệu nhạy cảm. DB/artifact thật ở local. MG làm kiến trúc, coding, review và giao việc; Agent Local chạy đúng task; Founder duyệt, merge và chuyển task. Không lưu bản sao tiến độ chi tiết trong README.

## North Star

`MARKET / SEARCH / MOTGU Signal -> NeedHypothesis -> Opportunity Map -> human selection -> Research + MOTGU material -> Journal/Artwork -> ContentExperiment -> Measure -> reviewed hypothesis revision`

Keyword Plan là công cụ con trong Research. Seed của Founder là giả thuyết, chưa phải sự thật về khách hàng.

> Mỗi nội dung giải quyết một nhu cầu/câu hỏi cụ thể của một nhóm người cụ thể, dựa trên bằng chứng, có giá trị riêng của MOTGU, đo được và tạo thêm hiểu biết về khách hàng.

## Local quickstart - môi trường mới

Không dùng quickstart để khởi tạo lại runtime M1 đang có. Với runtime hiện hữu, đọc `AI_context.MD` và task chính xác trước; không ghi đè `.env`, không xóa volume, không tự migrate DB vận hành.

Chỉ với môi trường mới và được phép thiết lập:

```sh
# Chi copy khi .env chua ton tai.
test -e .env || cp .env.example .env
make setup
make db-up
make migrate
```

Backend và frontend ở hai terminal riêng. Backend và PostgreSQL mặc định chỉ bind loopback:

```sh
# Terminal 1
make backend-dev
```

```sh
# Terminal 2
make frontend-dev
```

Địa chỉ local: frontend `http://localhost:3000`, backend health `http://localhost:8000/health`, DB health `/health/db`, version `/version`, operational preflight `/system/preflight`.

### Kiểm thử an toàn

`make check` yêu cầu `TEST_DATABASE_URL` riêng, fail-closed nếu target thiếu/không an toàn, tự tạo database test khi cần và migrate database test trước pytest. Không trỏ `TEST_DATABASE_URL` vào DB vận hành.

```sh
make check
```

Có thể chạy riêng bước chuẩn bị test DB:

```sh
make test-db-prepare
```

### Preflight, backup và restore-test

Preflight không in secret/connection string:

```sh
make ops-preflight
```

Backup mặc định ghi ngoài repository tại `~/.local/share/contentengine/backups`. Có thể đổi bằng `CONTENTENGINE_BACKUP_DIR`. Không commit dump/manifest vào Git:

```sh
make backup
```

Mỗi backup có custom-format PostgreSQL dump và manifest SHA-256 + fingerprint lineage. Kiểm chứng restore luôn dùng database disposable có tên chứa `restore_test`, so khớp ContentCase/ContentRun/Approval/Artifact/ContentVersion + artifact hash/lineage hash, đồng thời kiểm tra DB nguồn không đổi:

```sh
make restore-test BACKUP=/absolute/path/contentengine-...dump
```

Restore DB mặc định bị xóa sau khi kiểm tra thành công/thất bại; script hỗ trợ `--keep` khi cần điều tra thủ công.

Thiết lập development không thay thế kiểm tra bảo mật: xác minh địa chỉ lắng nghe, không mở cổng ra internet, không đưa `.env`, API key, phiên đăng nhập hay DB dump lên GitHub.

## Phạm vi V1

Trong phạm vi: MOTGU-first; Journal; Artwork; ContentCase/Evidence chung với LocaleVariant VI/EN viết độc lập; Brand/Language DNA; Discovery/Evidence Research; Opportunity Map mini; Evidence Ledger; durable harness/checkpoint; quality evaluation; Content Memory; Golden/regression; human approval; WordPress handoff; học theo chu kỳ 1/3/6 tháng.

Ngoài phạm vi: CRM, sales/customer-care agent, vận hành đa kênh, workflow automation tổng quát, multi-project UI, kho keyword khổng lồ, backlink/difficulty suite, tự đổi luật/prompt hoặc xuất bản mà không có người duyệt.

## Kiến trúc

`Configuration -> ContentCase/LocaleVariant -> Knowledge Recall -> Discovery/Opportunity -> EvidenceSet + OriginalityPack -> Durable Harness -> Content Workflow -> Assertion Audit + Human Approval -> Publish -> Measure -> reviewed Learning`

Dùng lại module và harness hiện có. Không cần cloud deployment để hoàn thành M1. Hoàn thành code không đồng nghĩa hoàn thành vận hành.

## Search và knowledge

Serper nhìn Google/PAA/Related/Autocomplete; Tavily tìm nguồn nghiên cứu; Exa cho nguồn sâu/second-hop; Jina đọc URL đã chọn; Brave chỉ optional fallback/coverage check. Không coi thứ hạng tìm kiếm là độ tin cậy.

`Raw source -> Knowledge Candidate -> dedupe + provenance + review -> Approved Knowledge -> optional Obsidian mirror`

Không đổ raw SERP/API data vào Obsidian. Mirror không tự trở thành nguồn chuẩn. Output AI không tự trở thành factual evidence.

## Tài liệu nền tảng

Quyết định lớn cần được khóa trong docs trước implementation. Đọc theo task, không đọc lại toàn bộ lịch sử mỗi lần:

- `docs/00-NORTH-STAR.md`, `docs/01-NON-NEGOTIABLES.md`, `docs/02-ARCHITECTURE-SPEC.md`.
- `docs/03-DATA-CONTRACT.md`, `docs/04-SETTINGS-CONTRACT.md`, `docs/05-HARNESS-SPEC.md`.
- `docs/06-MEMORY-LEARNING-SPEC.md`, `docs/07-QUALITY-EVAL-SPEC.md`.
- `docs/08-JOURNAL-SPEC.md`, `docs/09-ARTWORK-SPEC.md`, `docs/10-PUBLISH-MEASURE-SPEC.md`.
- `docs/11-RESEARCH-SEARCH-SPEC.md`, `docs/12-OPPORTUNITY-MAP-SPEC.md`, `docs/19-CE05-JOURNAL-ENGINE-SPEC.md`.
- `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md`, `docs/PLAN.md`, `docs/TASKS.md`, `docs/CHECKLIST.md`, `docs/TASK-HARNESS.md`.

CE01 walking-skeleton runbook và `docs/logs/` giữ bằng chứng lịch sử, không thay thế trạng thái hiện tại.

ContentEngine học provenance, chống trùng, bounded context, checkpoint/resume, telemetry và human-approved learning từ OpenHuman; không sao chép toàn bộ kiến trúc hoặc sản phẩm: <https://github.com/tinyhumansai/openhuman>.