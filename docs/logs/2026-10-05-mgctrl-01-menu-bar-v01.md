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
- No background status polling. Refresh happens on menu open and once after a confirmed mutation.
- Ambiguous/lost mutation response is not resent automatically.
- Finder `MG Control.app` packaging is included as a local ignored artifact.
- Founder later authorized MC-05 in the same workstream after observing disabled Start/Stop controls.

## MC-05 Start/Stop boundary

MC-05 is implemented with dedicated `launchd` ownership instead of ad-hoc process discovery:

- Start refuses backend/frontend that are already responding outside MG ownership.
- Start validates backend venv, frontend dependencies and production build.
- Start may run `docker compose up -d --wait postgres`; it does not migrate the DB.
- Start requires `scripts.ops_release_preflight` to PASS before runtime bootstrap.
- Backend and frontend are registered under dedicated MG labels and run immediately.
- Operator worker is registered under a dedicated MG label with `RunAtLoad=false`; confirmed workflow commands with a `job_id` kick one one-shot worker, so MG does not introduce a persistent polling worker loop.
- Stop only boots out MG-owned labels. It does not stop PostgreSQL, delete data, mutate history or kill external runtime.
- Lifecycle status uses one-shot `launchctl print` calls; no continuous `sleep/ps/pgrep` polling.
- LaunchAgent environment is minimal and secret-free by construction.
- Missing/partial/ambiguous ownership fails closed.

## Verification required

Pre-MC-05 exact-SHA proof already established Swift build/tests, Finder app packaging, native UI, read-only API integration and OCR. Because MC-05 changes runtime ownership, a fresh exact-SHA Agent Local proof is required before merge:

- `swift build` + `swift test`;
- exact-ref OCR for the MC-05 diff;
- safe Start/Stop proof in a disposable/non-operational environment;
- verify backend/frontend labels run and worker label remains on-demand when idle;
- verify a synthetic/test confirmed command can kick one worker once if a disposable test lineage is available;
- prove Stop removes only MG labels and leaves PostgreSQL/data untouched;
- rebuild and reinstall `MG Control.app` in Founder repo root.

## Stop condition

Do not merge until the new MC-05 exact SHA passes local verification. Do not authorize operational migration, WordPress/publish or destructive DB/process actions as part of this slice.
