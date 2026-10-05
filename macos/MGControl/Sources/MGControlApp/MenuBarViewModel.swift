import AppKit
import Foundation
import MGControlCore

@MainActor
final class MenuBarViewModel: ObservableObject {
    @Published private(set) var snapshot = ControlSnapshot(
        engineStatus: .unknown,
        summary: nil,
        needsMe: [],
        actionTargets: .empty,
        message: nil
    )
    @Published private(set) var lifecycleStatus = ManagedRuntimeStatus.stopped
    @Published private(set) var lifecycleMessage: String?
    @Published private(set) var isBusy = false
    @Published private(set) var actionInFlight: OperatorIntent?

    let config: AppConfig
    private let service: ControlService
    private let lifecycle: LifecycleController

    init(
        config: AppConfig,
        service: ControlService,
        lifecycle: LifecycleController
    ) {
        self.config = config
        self.service = service
        self.lifecycle = lifecycle
    }

    var needsMeCount: Int {
        snapshot.summary?.counts.needsHuman ?? snapshot.needsMe.count
    }

    var displayEngineStatus: EngineStatus {
        switch lifecycleStatus.state {
        case .running:
            return snapshot.engineStatus == .running ? .running : .starting
        case .starting:
            return .starting
        case .partial:
            return .error
        case .stopped:
            if snapshot.engineStatus == .running {
                return .external
            }
            return snapshot.engineStatus
        }
    }

    var displayMessage: String? {
        if let lifecycleMessage {
            return lifecycleMessage
        }

        switch lifecycleStatus.state {
        case .partial:
            return "Runtime MG đang không đầy đủ. Bấm Dừng để dọn các dịch vụ do MG quản lý."
        case .running, .starting:
            if snapshot.engineStatus != .running {
                return "Dịch vụ do MG quản lý đã được gọi; đang chờ API sẵn sàng."
            }
        case .stopped:
            if snapshot.engineStatus == .running {
                return "ContentEngine đang chạy ngoài MG Control; MG sẽ không tự dừng runtime này."
            }
        }

        return snapshot.message
    }

    var canStartEngine: Bool {
        lifecycleStatus.state == .stopped &&
        snapshot.engineStatus != .running &&
        !isBusy
    }

    var canStopEngine: Bool {
        lifecycleStatus.ownsRuntime && !isBusy
    }

    var continueTarget: OperatorActionTarget? {
        snapshot.actionTargets.continueTarget
    }

    var retryTarget: OperatorActionTarget? {
        snapshot.actionTargets.retryTarget
    }

    var cancelTarget: OperatorActionTarget? {
        snapshot.actionTargets.cancelTarget
    }

    func refresh() async {
        guard !isBusy else { return }
        isBusy = true
        lifecycleMessage = nil

        async let nextSnapshot = service.refresh()
        async let nextLifecycle = lifecycle.status()

        snapshot = await nextSnapshot
        lifecycleStatus = await nextLifecycle
        isBusy = false
    }

    func startEngine() async {
        guard !isBusy else { return }
        isBusy = true
        lifecycleMessage = "Đang khởi động ContentEngine…"

        do {
            lifecycleStatus = try await lifecycle.start()
            lifecycleMessage = nil
            snapshot = await service.refresh()
        } catch {
            lifecycleStatus = await lifecycle.status()
            lifecycleMessage = localized(error)
        }

        isBusy = false
    }

    func stopEngine() async {
        guard !isBusy else { return }
        isBusy = true
        lifecycleMessage = "Đang dừng các dịch vụ do MG quản lý…"

        do {
            lifecycleStatus = try await lifecycle.stop()
            lifecycleMessage = nil
            snapshot = await service.refresh()
        } catch {
            lifecycleStatus = await lifecycle.status()
            lifecycleMessage = localized(error)
        }

        isBusy = false
    }

    func perform(_ target: OperatorActionTarget) async {
        guard !isBusy else { return }
        isBusy = true
        actionInFlight = target.intent
        lifecycleMessage = nil

        do {
            _ = try await service.perform(target: target)
            actionInFlight = nil
            snapshot = await service.refresh()
            lifecycleStatus = await lifecycle.status()
        } catch {
            actionInFlight = nil
            snapshot = ControlSnapshot(
                engineStatus: .unknown,
                summary: snapshot.summary,
                needsMe: snapshot.needsMe,
                actionTargets: .empty,
                message: "Kết quả thao tác chưa xác định. Không tự gửi lại; hãy mở Sản xuất để kiểm tra."
            )
        }

        isBusy = false
    }

    func open(_ route: QuickRoute) {
        NSWorkspace.shared.open(route.url(baseURL: config.webBaseURL))
    }

    func quit() {
        NSApplication.shared.terminate(nil)
    }

    private func localized(_ error: Error) -> String {
        if let value = error as? LocalizedError,
           let description = value.errorDescription,
           !description.isEmpty {
            return description
        }
        return "Thao tác hệ thống thất bại. Mở Hệ thống để kiểm tra."
    }
}
