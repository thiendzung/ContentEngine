import AppKit
import MGControlCore
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
    }
}

@main
struct MGControlApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model: MenuBarViewModel

    init() {
        let config = AppConfig.load()
        let client = ContentEngineClient(config: config)
        let service = ControlService(client: client)
        let lifecycle = LifecycleController(config: config)
        _model = StateObject(
            wrappedValue: MenuBarViewModel(
                config: config,
                service: service,
                lifecycle: lifecycle
            )
        )
    }

    var body: some Scene {
        MenuBarExtra {
            MenuBarView(model: model)
        } label: {
            Text("MG")
                .font(.system(size: 12, weight: .bold, design: .rounded))
        }
        .menuBarExtraStyle(.window)
    }
}
