import MGControlCore
import SwiftUI

struct MenuBarView: View {
    @ObservedObject var model: MenuBarViewModel

    var body: some View {
        VStack(spacing: 0) {
            statusHeader
            Divider()
            controlStrip
            Divider()
            quickMenu
            Divider()
            footer
        }
        .frame(width: 330)
        .background(.regularMaterial)
        .task {
            await model.refresh()
        }
    }

    private var statusHeader: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text("ContentEngine")
                    .font(.headline)
                if let message = model.displayMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }
            }

            Spacer(minLength: 12)

            HStack(spacing: 6) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                Text(model.displayEngineStatus.vietnameseLabel)
                    .font(.subheadline.weight(.medium))
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var controlStrip: some View {
        HStack(spacing: 8) {
            ControlIconButton(
                systemImage: "play.fill",
                title: "Khởi động ContentEngine",
                color: .green,
                enabled: model.canStartEngine
            ) {
                Task { await model.startEngine() }
            }

            ControlIconButton(
                systemImage: "stop.fill",
                title: "Dừng ContentEngine",
                color: .red,
                enabled: model.canStopEngine
            ) {
                Task { await model.stopEngine() }
            }

            Divider()
                .frame(height: 22)

            ControlIconButton(
                systemImage: primaryWorkflowPresentation.systemImage,
                title: primaryWorkflowHelp,
                color: primaryWorkflowColor,
                enabled: model.continueTarget != nil && !model.isBusy
            ) {
                guard let target = model.continueTarget else { return }
                Task { await model.perform(target) }
            }

            ControlIconButton(
                systemImage: "arrow.clockwise",
                title: retryHelp,
                color: .orange,
                enabled: model.retryTarget != nil && !model.isBusy
            ) {
                guard let target = model.retryTarget else { return }
                Task { await model.perform(target) }
            }

            ControlIconButton(
                systemImage: "xmark",
                title: cancelHelp,
                color: .red,
                enabled: model.cancelTarget != nil && !model.isBusy
            ) {
                guard let target = model.cancelTarget else { return }
                Task { await model.perform(target) }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private var quickMenu: some View {
        VStack(spacing: 2) {
            QuickMenuRow(
                route: .needsMe,
                trailingCount: model.needsMeCount
            ) {
                model.open(.needsMe)
            }

            QuickMenuRow(route: .newJournal) {
                model.open(.newJournal)
            }

            QuickMenuRow(route: .production) {
                model.open(.production)
            }

            QuickMenuRow(route: .contentMap) {
                model.open(.contentMap)
            }

            QuickMenuRow(route: .system) {
                model.open(.system)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 7)
    }

    private var footer: some View {
        VStack(spacing: 2) {
            QuickMenuRow(route: .dashboard) {
                model.open(.dashboard)
            }

            Button {
                model.quit()
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: "power")
                        .frame(width: 18)
                    Text("Thoát MG")
                    Spacer()
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 10)
            .frame(height: 34)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 7)
    }

    private var statusColor: Color {
        switch model.displayEngineStatus {
        case .starting:
            return .blue
        case .running:
            return .green
        case .external:
            return .orange
        case .stopped:
            return .secondary
        case .error:
            return .red
        case .unknown:
            return .orange
        }
    }

    private var primaryWorkflowPresentation: PrimaryWorkflowControlPresentation {
        ControlPresentation.primaryWorkflow(
            for: model.continueTarget?.intent
        )
    }

    private var primaryWorkflowHelp: String {
        guard let target = model.continueTarget else {
            return primaryWorkflowPresentation.title
        }
        return "\(primaryWorkflowPresentation.title) — \(target.title)"
    }

    private var primaryWorkflowColor: Color {
        switch model.continueTarget?.intent {
        case .start:
            return .purple
        case .continueWork:
            return .blue
        case .resume:
            return .cyan
        case .retry, .cancel, .none:
            return .secondary
        }
    }

    private var retryHelp: String {
        guard let target = model.retryTarget else {
            return "Chưa có bước có thể thử lại"
        }
        return "Thử lại bước hiện tại — \(target.title)"
    }

    private var cancelHelp: String {
        guard let target = model.cancelTarget else {
            return "Chưa có tác vụ có thể hủy"
        }
        return "Hủy tác vụ đang chờ — \(target.title)"
    }
}

private struct ControlIconButton: View {
    let systemImage: String
    let title: String
    let color: Color
    let enabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(enabled ? color : Color.secondary)
                .frame(width: 38, height: 30)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.primary.opacity(enabled ? 0.07 : 0.035))
                )
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .help(title)
        .accessibilityLabel(Text(title))
    }
}

private struct QuickMenuRow: View {
    let route: QuickRoute
    var trailingCount: Int? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: route.systemImage)
                    .frame(width: 18)
                    .foregroundStyle(.secondary)

                Text(route.title)

                Spacer()

                if let trailingCount, trailingCount > 0 {
                    Text("\(trailingCount)")
                        .font(.caption.weight(.semibold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(
                            Capsule()
                                .fill(Color.orange.opacity(0.18))
                        )
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 10)
        .frame(height: 34)
        .accessibilityLabel(
            trailingCount.map { Text("\(route.title), \($0)") } ?? Text(route.title)
        )
    }
}
