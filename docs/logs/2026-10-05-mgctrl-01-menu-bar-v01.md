# MGCTRL-01 — macOS Menu Bar Control v0.1

Date: 2026-10-05  
Founder authorization: implement the compact macOS menu-bar control now; focus on execution.

## Goal

Add a native macOS menu-bar remote control for ContentEngine with the text icon `MG`, 100% Vietnamese UI, compact semantic action icons, and quick links to frequent operator areas.

## Exact base

- Repository: `thiendzung/ContentEngine`
- Base: `dca2efc19879be6dba70d6c5b7765ad766be5349`
- Branch: `feat/mgctrl-01-menu-bar-v01`
- Tracking: issue #327

## Implemented scope

- SwiftPM macOS 13+ package under `macos/MGControl/`.
- Native SwiftUI `MenuBarExtra` with menu-bar label `MG`.
- Accessory app policy; no Dock app surface.
- Compact Vietnamese popover.
- Five icon controls with tooltip/accessibility label:
  - Khởi động
  - Dừng hệ thống
  - Tiếp tục
  - Thử lại
  - Hủy tác vụ
- Read-only integration:
  - `GET /control-center/summary`
  - `GET /control-center/needs-me`
  - `GET /journal/production-board`
  - `GET /journal/operator/cases/{id}`
- Mutation integration:
  - `POST /journal/operator/cases/{id}/commands`
  - exact `expected_state_version`
  - per-request `idempotency_key`
- Continue/Retry/Cancel fail closed when no unique backend-authorized target exists.
- Quick menu:
  - Việc cần tôi
  - Tạo bài mới
  - Sản xuất
  - Bản đồ nội dung
  - Hệ thống
  - Mở ContentEngine
- No background polling. Refresh happens on menu open and once after a confirmed mutation.
- Ambiguous/lost mutation response is not resent automatically.
- Start/Stop controls are rendered but intentionally disabled in this slice.

## Start/Stop boundary

MC-05 is not enabled yet because current operational lifecycle is safety-sensitive and operational DB/runtime activation remains separately authorized. Do not wire Start/Stop to ad-hoc shell/process discovery.

When MC-05 is opened, it must:
- preserve operational DB/history;
- own only processes it starts or use an explicitly reviewed lifecycle authority;
- use termination callbacks/event-driven lifecycle;
- never use continuous `sleep/ps/pgrep` polling;
- fail closed if process ownership is ambiguous.

## Verification required

Not run remotely:
- `swift build`
- `swift test`
- real macOS MenuBarExtra visual proof
- real ContentEngine local API integration
- dark/light mode
- repeated app open/quit
- exact-ref OCR if applicable to this UI slice

Agent Local must run those checks on the exact candidate SHA before MG can state READY TO MERGE.

## Stop condition

Stop after v0.1 shell + read-only state + quick menu + safe Continue/Retry/Cancel are implemented and a PR is prepared. Do not activate operational migration, WordPress/publish, or Start/Stop process lifecycle in this slice.
