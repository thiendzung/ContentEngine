# MG Control v0.1

Tiện ích macOS trên thanh menu để thao tác nhanh với ContentEngine.

## Phạm vi hiện tại

- icon chữ `MG` trên thanh menu;
- giao diện 100% tiếng Việt;
- đọc `Control Center`, `Việc cần tôi` và trạng thái Operator;
- `Khởi động / Dừng hệ thống` điều khiển runtime local do MG quản lý;
- `Tiếp tục / Thử lại / Hủy tác vụ` chỉ bật khi backend cho phép;
- menu nhanh: Việc cần tôi, Tạo bài mới, Sản xuất, Bản đồ nội dung, Hệ thống;
- không polling nền; trạng thái lifecycle dùng `launchd` one-shot + callback/process exit;
- không tự retry mutation khi kết quả mạng không rõ;
- không tự dừng runtime đang chạy ngoài quyền quản lý của MG.

## Khởi động / Dừng hệ thống

`Khởi động` thực hiện theo thứ tự fail-closed:

1. xác định đúng repo chứa `MG Control.app`;
2. từ chối nếu backend/frontend đang chạy ngoài MG;
3. kiểm tra backend venv, frontend dependencies và production build;
4. chạy `docker compose up -d --wait postgres` để bảo đảm PostgreSQL sẵn sàng, không migrate;
5. chạy `scripts.ops_release_preflight`;
6. chỉ khi preflight PASS mới bootstrap ba job `launchd` riêng của MG:
   - backend;
   - frontend production;
   - operator worker hiện có.

`Dừng hệ thống` chỉ `bootout` đúng ba job có label của MG. PostgreSQL, DB/history và runtime bên ngoài MG không bị dừng/xóa.

Nếu runtime đang chạy ngoài MG, trạng thái hiển thị **Đang chạy ngoài MG**; nút Dừng bị khóa để tránh kill nhầm process.

## Mở bằng icon trong Finder

Từ repo root, tạo app bundle local một lần:

```sh
zsh macos/MGControl/package-app.zsh
```

Sau đó repo root sẽ có:

```text
MG Control.app
```

Chỉ cần double-click **MG Control.app** trong Finder để mở MG Control. App bundle được build release, có icon chữ **MG**, chạy dạng menu-bar accessory và không hiện Dock icon.

`MG Control.app` là artifact local nên được gitignore; khi source MG Control thay đổi, chạy lại lệnh package để cập nhật app.

## Chạy local

```sh
cd macos/MGControl
swift run MGControl
```

Mặc định:

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`
- Project: `motgu`
- Timezone: timezone hiện tại của macOS
- Repo root: tự nhận từ vị trí `MG Control.app` hoặc tìm ngược từ current working directory.

Có thể đổi bằng biến môi trường:

```sh
CONTENTENGINE_API_URL=http://127.0.0.1:8000 \
CONTENTENGINE_WEB_URL=http://127.0.0.1:3000 \
CONTENTENGINE_PROJECT_SLUG=motgu \
CONTENTENGINE_TIMEZONE=Asia/Ho_Chi_Minh \
CONTENTENGINE_REPO_ROOT=/Users/thiendung/MOTGU-AI/ContentEngine \
swift run MGControl
```

## Nguyên tắc an toàn

MG Control không có workflow engine riêng. Backend ContentEngine vẫn quyết định semantic action hợp lệ và mọi mutation dùng `expected_state_version` + `idempotency_key`.

Lifecycle control không dùng `sleep/ps/pgrep` polling. MG chỉ quản lý các service mang label riêng `com.motgu.contentengine.mg.*` và fail closed khi ownership không rõ.
