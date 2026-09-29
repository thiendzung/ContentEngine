# ContentEngine

ContentEngine là hệ thống sản xuất nội dung có kiểm soát cho MOTGU: từ câu hỏi thật của khách hàng -> bằng chứng -> Angle -> Outline -> Writer -> Human Voice -> kiểm tra chất lượng -> Founder duyệt -> publish/đo lường khi được cho phép.

Mục tiêu không phải viết thật nhiều bài. Mục tiêu là tạo Pillar/Cluster và Artwork/Journal **đúng, hữu ích, có giọng MOTGU, có nguồn gốc rõ ràng và không tự bịa thêm sự thật**.

## Chạy local đơn giản nhất

### 1. Chuẩn bị một lần

Yêu cầu: Docker, Python 3.12, Node.js/npm.

```sh
cd /Users/thiendung/MOTGU-AI/ContentEngine

# Chỉ tạo .env nếu máy chưa có.
test -e .env || cp .env.example .env

make setup
```

Nếu PostgreSQL của ContentEngine **chưa chạy**, khởi động nó:

```sh
make db-up
```

Không chạy `make migrate` trên máy vận hành hiện tại chỉ để "cho đồng bộ". DB vận hành có quy trình migration riêng và cần Founder cho phép.

### 2. Dùng DB test an toàn

Lệnh này chỉ được phép reset database trong `TEST_DATABASE_URL`, không phải DB vận hành:

```sh
make test-db-reset
```

Repo mặc định phân tách:

- `DATABASE_URL`: dữ liệu vận hành/local thật.
- `TEST_DATABASE_URL`: database test có thể xóa và dựng lại.
- `APP_ENV=test`: buộc backend dùng `TEST_DATABASE_URL`.

### 3. Chạy giao diện

Mở hai Terminal.

**Terminal 1 — backend dùng DB test**

```sh
cd /Users/thiendung/MOTGU-AI/ContentEngine
APP_ENV=test make backend-dev
```

**Terminal 2 — frontend**

```sh
cd /Users/thiendung/MOTGU-AI/ContentEngine
make frontend-dev
```

Mở:

- Giao diện: <http://localhost:3000>
- Backend health: <http://localhost:8000/health>
- DB health: <http://localhost:8000/health/db>
- Version: <http://localhost:8000/version>
- Preflight: <http://localhost:8000/system/preflight>

### 4. Khi cần xử lý một job

Worker mặc định chỉ claim và xử lý **một job** rồi thoát:

```sh
cd /Users/thiendung/MOTGU-AI/ContentEngine
APP_ENV=test make operator-worker
```

Không cần chạy worker liên tục khi chỉ xem giao diện. Không dùng polling để chờ trạng thái.

### 5. Dừng local

Dừng backend/frontend bằng `Ctrl-C`.

Nếu muốn dừng PostgreSQL Compose nhưng giữ nguyên volume:

```sh
make db-down
```

**Không chạy** `docker compose down -v` hoặc xóa volume nếu chưa có task riêng cho việc đó.

## Chạy test

Toàn bộ gate local:

```sh
make check
```

Riêng backend:

```sh
make backend-check
```

Riêng frontend:

```sh
make frontend-check
```

`make check` sẽ reset/migrate database test trước pytest. Không được trỏ `TEST_DATABASE_URL` vào DB vận hành.

## Quy tắc an toàn trên máy hiện tại

Các lệnh dưới đây **không phải quickstart** và không được chạy chỉ để thử:

- `make migrate`
- `make operational-migrate`
- `make operational-migrate-0042`
- release lifecycle trên DB vận hành
- WordPress publish
- `docker compose down -v`
- xóa PostgreSQL volume

Backup/recovery phải nằm ngoài repository. Mặc định backup được ghi tại:

```text
~/.local/share/contentengine/backups
```

Không commit `.env`, secret, dump, private artifact hoặc recovery evidence lên GitHub.

## Pipeline hiện tại

```text
Customer Truth / Research
        |
        v
Content Opportunity + Promise Coverage
        |
        v
Pillar / Cluster role
        |
        v
Evidence + Originality
        |
        v
Angle -> Founder duyệt
        |
        v
Outline -> Founder duyệt
        |
        v
Writer -> Human Voice
        |
        v
Assertion Audit + Source Copy
        |
        v
Reader Value + Search/AI readiness
        |
        v
Deep Quality
        |
        v
Founder final review
        |
        v
Publish / Measure / Learning
```

Các gate của Founder không được tự động bỏ qua. Final approval cũng không đồng nghĩa có quyền publish.

## Nguyên tắc chất lượng

- Một nội dung phải giải quyết một câu hỏi/nhu cầu cụ thể.
- Pillar có độ rộng hữu ích; Cluster đi sâu vào một vấn đề hẹp hơn.
- Search/SEO/AEO/AIO/GEO không được thắng Truth hoặc Reader Value.
- Human Voice được cải thiện nhịp, độ tự nhiên và chi tiết đã có nguồn; không được sáng tác thêm ký ức, lời nói, ý định nghệ sĩ, giá, chính sách hay sự kiện.
- Evidence/Originality phải có provenance; output AI không tự trở thành bằng chứng.
- VI và EN là hai lane độc lập, không phải dịch máy qua lại.
- Artwork/Artist/Visit/Workshop/Inquiry là next step khi phù hợp, không nhồi CTA vào mọi bài.

## Kiến trúc ngắn gọn

- Backend: Python + FastAPI.
- Frontend: Next.js + React.
- DB: PostgreSQL.
- Migration: Alembic.
- Runtime chính: local-first.
- WordPress: publishing target bên ngoài, chỉ dùng khi được cấp quyền.
- GitHub: source code, contract, issue/PR và sanitized evidence.
- DB thật, secret, recovery dump và private artifact: giữ local.

## Tài liệu cần đọc

Không cần đọc toàn bộ `docs/logs/` để chạy repo.

Ưu tiên:

1. `AI_context.MD` — working window hiện tại.
2. `docs/PLAN.md` — thứ tự công việc.
3. `docs/TASKS.md` — tiến độ.
4. `docs/CHECKLIST.md` — gate kiểm tra.
5. `AGENTS.md` — vai trò Founder / MG / Agent Local.
6. `docs/20-LOCAL-FIRST-DELIVERY-SPEC.md` — quy tắc vận hành local.

Các file trong `backend/migrations/versions/` là lịch sử schema cần thiết để dựng DB; không coi chúng là file SQL rác để dọn.

## Phân vai

- **Founder:** quyết định sản phẩm/editorial, cấp quyền tác vụ nhạy cảm và merge.
- **MG / ChatGPT:** kiến trúc, coding, test cho thay đổi, review, chuẩn bị PR và đánh giá bằng chứng Agent Local.
- **Agent Local:** sync exact SHA, chạy test/runtime/DB/OCR trên máy thật và trả bằng chứng; chỉ sửa code khi được giao phạm vi cụ thể.
- **GitHub Actions:** confirmation gate ngắn; heavy verification ưu tiên Agent Local.

## Khi chuẩn bị một PR

```text
code
-> focused tests
-> self-review
-> CI confirmation
-> exact-ref OpenCodeReview
-> Agent Local exact-head proof khi cần
-> Founder merge
```

Không merge dựa trên tên PR, số lượng test hay trạng thái “looks good” nếu exact HEAD chưa được chứng minh.
