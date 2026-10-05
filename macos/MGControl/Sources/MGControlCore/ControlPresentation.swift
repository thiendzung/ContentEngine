import Foundation

public struct PrimaryWorkflowControlPresentation: Equatable, Sendable {
    public let systemImage: String
    public let title: String

    public init(
        systemImage: String,
        title: String
    ) {
        self.systemImage = systemImage
        self.title = title
    }
}

public enum ControlPresentation {
    public static func primaryWorkflow(
        for intent: OperatorIntent?
    ) -> PrimaryWorkflowControlPresentation {
        switch intent {
        case .start:
            return PrimaryWorkflowControlPresentation(
                systemImage: "play.circle.fill",
                title: "Bắt đầu bài"
            )
        case .continueWork:
            return PrimaryWorkflowControlPresentation(
                systemImage: "forward.fill",
                title: "Tiếp tục bài"
            )
        case .resume:
            return PrimaryWorkflowControlPresentation(
                systemImage: "playpause.fill",
                title: "Tiếp tục lại"
            )
        case .retry, .cancel, .none:
            return PrimaryWorkflowControlPresentation(
                systemImage: "forward.fill",
                title: "Chưa có bước tiếp tục"
            )
        }
    }
}
