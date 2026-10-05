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
    @Published private(set) var isBusy = false
    @Published private(set) var actionInFlight: OperatorIntent?

    let config: AppConfig
    private let service: ControlService

    init(
        config: AppConfig,
        service: ControlService
    ) {
        self.config = config
        self.service = service
    }

    var needsMeCount: Int {
        snapshot.summary?.counts.needsHuman ?? snapshot.needsMe.count
    }

    var canStartEngine: Bool {
        false
    }

    var canStopEngine: Bool {
        false
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
        snapshot = await service.refresh()
        isBusy = false
    }

    func perform(_ target: OperatorActionTarget) async {
        guard !isBusy else { return }
        isBusy = true
        actionInFlight = target.intent

        do {
            _ = try await service.perform(target: target)
            actionInFlight = nil
            snapshot = await service.refresh()
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
}
