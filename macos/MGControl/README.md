# MG Control v0.1

Tiện ích macOS trên thanh menu để thao tác nhanh với ContentEngine.

## Phạm vi hiện tại

- icon chữ `MG` trên thanh menu;
- giao diện 100% tiếng Việt;
- đọc `Control Center`, `Việc cần tôi` và trạng thái Operator;
- `Tiếp tục / Thử lại / Hủy tác vụ` chỉ bật khi backend cho phép;
- menu nhanh: Việc cần tôi, Tạo bài mới, Sản xuất, Bản đồ nội dung, Hệ thống;
- không polling nền; làm mới khi mở control và sau mutation thành công;
- không tự retry mutation khi kết quả mạng không rõ;
- `Khởi động / Dừng hệ thống` đã có vị trí UI nhưng cố ý chưa bật cho tới MC-05, vì lifecycle operational hiện phải được khóa với release/runtime thật trước khi cho phép điều khiển tiến trình.

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

Có thể đổi bằng biến môi trường:

```sh
CONTENTENGINE_API_URL=http://127.0.0.1:8000 \
CONTENTENGINE_WEB_URL=http://127.0.0.1:3000 \
CONTENTENGINE_PROJECT_SLUG=motgu \
CONTENTENGINE_TIMEZONE=Asia/Ho_Chi_Minh \
swift run MGControl
```

## Nguyên tắc an toàn

MG Control không có workflow engine riêng. Backend ContentEngine vẫn quyết định semantic action hợp lệ và mọi mutation dùng `expected_state_version` + `idempotency_key`.
